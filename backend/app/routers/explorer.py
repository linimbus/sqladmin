from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from ..deps import ensure_writable, load_connection
from ..models import Connection
from ..schemas import (
    CatalogOut,
    MutationResult,
    OverviewOut,
    RowMutation,
    RowsOut,
    TableDetail,
    TablesOut,
)
from ..services.connections import sanitize_error
from ..services.introspect import (
    completion_schema,
    delete_row,
    export_query,
    get_rows,
    insert_row,
    list_catalogs,
    list_tables,
    overview,
    table_detail,
    update_row,
)
from ..services.serialize import serialize_value

router = APIRouter(prefix="/connections/{connection_id}", tags=["explorer"])


def _fail(exc: BaseException) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(status_code=400, detail=sanitize_error(exc))
    return HTTPException(status_code=500, detail=sanitize_error(exc))


@router.get("/catalogs", response_model=CatalogOut)
def get_catalogs(
    database: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    try:
        return list_catalogs(connection, database)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.get("/tables", response_model=TablesOut)
def get_tables(
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    try:
        return list_tables(connection, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.get("/tables/{table}", response_model=TableDetail)
def get_table_detail(
    table: str,
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    try:
        return table_detail(connection, table, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.get("/tables/{table}/rows", response_model=RowsOut)
def get_table_rows(
    table: str,
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1),
    order_by: Optional[str] = Query(default=None),
    order_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    where: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    try:
        return get_rows(
            connection,
            table,
            database=database,
            schema=schema,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_dir=order_dir,
            where=where,
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.post("/tables/{table}/rows", response_model=MutationResult, status_code=201)
def create_table_row(
    table: str,
    payload: RowMutation,
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    ensure_writable(connection)
    try:
        return insert_row(connection, table, payload.values, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.put("/tables/{table}/rows", response_model=MutationResult)
def update_table_row(
    table: str,
    payload: RowMutation,
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    ensure_writable(connection)
    try:
        return update_row(connection, table, payload.values, payload.pk, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.delete("/tables/{table}/rows", response_model=MutationResult)
def delete_table_row(
    table: str,
    payload: RowMutation,
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    ensure_writable(connection)
    try:
        return delete_row(connection, table, payload.pk, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


def _csv_cell(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    value = serialize_value(value)
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@router.get("/tables/{table}/export")
def export_table(
    table: str,
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    order_by: Optional[str] = Query(default=None),
    order_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    where: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
):
    try:
        engine, reflected, statement = export_query(
            connection,
            table,
            database=database,
            schema=schema,
            order_by=order_by,
            order_dir=order_dir,
            where=where,
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        with engine.connect() as db_connection:
            result = db_connection.execution_options(stream_results=True).execute(statement)
            header = [str(key) for key in result.keys()]
            yield "\ufeff"
            writer.writerow(header)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            for row in result.yield_per(500):
                writer.writerow([_csv_cell(value) for value in row])
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{reflected.name}_{timestamp}.csv"
    headers = {
        "Content-Disposition": (
            f'attachment; filename="{quote(filename)}"; '
            f"filename*=UTF-8''{quote(filename)}"
        )
    }
    return StreamingResponse(generate(), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/completion")
def get_completion(
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, List[str]]:
    try:
        return completion_schema(connection, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc


@router.get("/overview", response_model=OverviewOut)
def get_overview(
    database: Optional[str] = Query(default=None),
    schema: Optional[str] = Query(default=None),
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    try:
        return overview(connection, database, schema)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc
