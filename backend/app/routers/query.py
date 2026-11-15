from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..deps import load_connection
from ..models import Connection
from ..schemas import QueryRequest, QueryResponse
from ..services.connections import sanitize_error
from ..services.executor import ReadOnlyViolation, execute_sql

router = APIRouter(prefix="/connections/{connection_id}", tags=["query"])


@router.post("/query", response_model=QueryResponse)
def run_query(
    payload: QueryRequest,
    connection: Connection = Depends(load_connection),
) -> Dict[str, Any]:
    try:
        return execute_sql(
            connection,
            payload.sql,
            max_rows=payload.max_rows,
            database=payload.database,
            schema=payload.schema_name,
        )
    except ReadOnlyViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=sanitize_error(exc)) from exc
