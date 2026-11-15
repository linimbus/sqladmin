from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import Column, MetaData, Table, func, inspect, select, text, types as sqltypes
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable

from ..config import MAX_PAGE_SIZE
from ..models import Connection
from .connections import get_engine, sanitize_error, server_version, size_pretty, sqlite_file_size
from .serialize import serialize_value

SYSTEM_MYSQL_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}


def _quote(engine: Engine, name: str) -> str:
    return engine.dialect.identifier_preparer.quote(name)


def _effective_schema(conn: Connection, schema: Optional[str]) -> Optional[str]:
    if conn.kind == "sqlite":
        return schema or "main"
    if conn.kind == "mysql":
        return None
    return schema or None


def list_catalogs(conn: Connection, database: Optional[str] = None) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    kind = conn.kind
    result: Dict[str, Any] = {
        "kind": kind,
        "current_database": database or conn.database,
        "databases": [],
        "schemas": [],
        "namespace": "schema",
    }

    with engine.connect() as connection:
        if kind == "sqlite":
            rows = connection.exec_driver_sql("PRAGMA database_list").fetchall()
            names = [row[1] for row in rows]
            result["databases"] = names
            result["schemas"] = ["main"]
            result["current_database"] = "main"
            result["namespace"] = "none"
            return result

        if kind == "mysql":
            result["namespace"] = "database"
            try:
                rows = connection.exec_driver_sql("SHOW DATABASES").fetchall()
                result["databases"] = [
                    row[0] for row in rows if row[0] not in SYSTEM_MYSQL_DATABASES
                ]
            except Exception:
                result["databases"] = []
            try:
                result["current_database"] = connection.exec_driver_sql("SELECT DATABASE()").scalar()
            except Exception:
                pass
            return result

        if kind == "postgresql":
            result["namespace"] = "schema"
            try:
                result["current_database"] = connection.exec_driver_sql(
                    "SELECT current_database()"
                ).scalar()
                result["databases"] = [
                    row[0]
                    for row in connection.exec_driver_sql(
                        "SELECT datname FROM pg_database "
                        "WHERE datistemplate = false ORDER BY datname"
                    ).fetchall()
                ]
            except Exception:
                pass
            try:
                result["schemas"] = [
                    row[0]
                    for row in connection.exec_driver_sql(
                        "SELECT nspname FROM pg_namespace "
                        "WHERE nspname NOT LIKE 'pg\\_%' ESCAPE '\\' "
                        "AND nspname <> 'information_schema' ORDER BY nspname"
                    ).fetchall()
                ]
            except Exception:
                result["schemas"] = ["public"]
            return result

        if kind == "mssql":
            result["namespace"] = "schema"
            try:
                result["current_database"] = connection.exec_driver_sql("SELECT DB_NAME()").scalar()
                result["databases"] = [
                    row[0]
                    for row in connection.exec_driver_sql(
                        "SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name"
                    ).fetchall()
                ]
            except Exception:
                pass
            try:
                result["schemas"] = [
                    row[0]
                    for row in connection.exec_driver_sql(
                        "SELECT name FROM sys.schemas "
                        "WHERE schema_id < 16384 AND name NOT IN ('sys', 'guest') ORDER BY name"
                    ).fetchall()
                ]
            except Exception:
                result["schemas"] = ["dbo"]
            return result

        if kind == "oracle":
            result["namespace"] = "schema"
            try:
                result["current_database"] = connection.exec_driver_sql(
                    "SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual"
                ).scalar()
                result["schemas"] = [
                    row[0]
                    for row in connection.exec_driver_sql(
                        "SELECT username FROM all_users ORDER BY username"
                    ).fetchall()
                ]
            except Exception:
                pass
            return result

    return result


def _mysql_table_meta(engine: Engine) -> Dict[str, Dict[str, Any]]:
    try:
        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT table_name, table_rows, table_comment, table_type "
                "FROM information_schema.tables WHERE table_schema = DATABASE()"
            ).fetchall()
        return {
            row[0]: {"rows": row[1], "comment": row[2], "type": row[3]}
            for row in rows
        }
    except Exception:
        return {}


def list_tables(
    conn: Connection, database: Optional[str] = None, schema: Optional[str] = None
) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    inspector = inspect(engine)

    table_names = inspector.get_table_names(schema=schema)
    try:
        view_names = inspector.get_view_names(schema=schema)
    except Exception:
        view_names = []

    meta: Dict[str, Dict[str, Any]] = _mysql_table_meta(engine) if conn.kind == "mysql" else {}

    def make_object(name: str, obj_type: str) -> Dict[str, Any]:
        info = meta.get(name, {})
        row_estimate = info.get("rows")
        return {
            "name": name,
            "type": obj_type,
            "schema": schema,
            "comment": info.get("comment") or None,
            "row_estimate": row_estimate if isinstance(row_estimate, int) else None,
        }

    tables = [make_object(name, "table") for name in sorted(table_names)]
    views = [make_object(name, "view") for name in sorted(view_names)]
    return {
        "database": database or conn.database,
        "schema": schema,
        "tables": tables,
        "views": views,
    }


def reflect_table(
    engine: Engine, table: str, schema: Optional[str] = None
) -> Table:
    metadata = MetaData()
    return Table(table, metadata, schema=schema, autoload_with=engine)


def _column_info(column: Column, pk_names: Iterable[str], kind: str) -> Dict[str, Any]:
    pk_list = list(pk_names)
    default = column.default
    if default is not None:
        default_repr = getattr(default, "arg", None)
        if default_repr is None:
            default_repr = str(default)
        default_str = str(default_repr)
    elif column.server_default is not None:
        default_str = str(column.server_default.arg)
    else:
        default_str = None

    autoincrement = bool(column.autoincrement is True)
    if (
        not autoincrement
        and kind == "sqlite"
        and column.primary_key
        and len(pk_list) == 1
        and isinstance(column.type, sqltypes.Integer)
        and default_str is None
    ):
        autoincrement = True

    return {
        "name": column.name,
        "type": str(column.type),
        "nullable": bool(column.nullable),
        "default": default_str,
        "primary_key": column.name in pk_list,
        "autoincrement": autoincrement,
        "computed": getattr(column, "computed", None) is not None,
        "comment": getattr(column, "comment", None),
        "length": getattr(column.type, "length", None),
    }


def _sqlite_ddl(engine: Engine, table: str, schema: Optional[str]) -> Optional[str]:
    master = f"{_quote(engine, schema)}.sqlite_master" if schema and schema != "main" else "sqlite_master"
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            f"SELECT sql FROM {master} WHERE name = ? AND type IN ('table', 'view')",
            (table,),
        ).fetchone()
    return row[0] if row else None


def _mysql_ddl(engine: Engine, table: str, is_view: bool) -> Optional[str]:
    db = engine.url.database
    if not db:
        return None
    qualified = f"{_quote(engine, db)}.{_quote(engine, table)}"
    statement = f"SHOW CREATE {'VIEW' if is_view else 'TABLE'} {qualified}"
    with engine.connect() as connection:
        row = connection.exec_driver_sql(statement).fetchone()
    if not row:
        return None
    return row[1] if len(row) > 1 else str(row[0])


def table_detail(
    conn: Connection,
    table: str,
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    inspector = inspect(engine)

    view_names = []
    try:
        view_names = inspector.get_view_names(schema=schema)
    except Exception:
        pass
    is_view = table in view_names
    obj_type = "view" if is_view else "table"

    reflected = reflect_table(engine, table, schema)
    pk_names = [column.name for column in reflected.primary_key.columns]
    columns = [_column_info(column, pk_names, conn.kind) for column in reflected.columns]

    try:
        indexes = [
            {
                "name": index.get("name") or "",
                "columns": index.get("column_names") or [],
                "unique": bool(index.get("unique")),
            }
            for index in inspector.get_indexes(table, schema=schema)
        ]
    except Exception:
        indexes = []

    try:
        foreign_keys = [
            {
                "name": fk.get("name"),
                "columns": fk.get("constrained_columns") or [],
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns") or [],
            }
            for fk in inspector.get_foreign_keys(table, schema=schema)
        ]
    except Exception:
        foreign_keys = []

    ddl = None
    try:
        if is_view:
            if conn.kind == "mysql":
                ddl = _mysql_ddl(engine, table, True)
            elif conn.kind == "sqlite":
                ddl = _sqlite_ddl(engine, table, schema)
        elif conn.kind == "sqlite":
            ddl = _sqlite_ddl(engine, table, schema)
        elif conn.kind == "mysql":
            ddl = _mysql_ddl(engine, table, False)
        else:
            ddl = str(CreateTable(reflected).compile(engine)).strip() + ";"
    except Exception:
        ddl = None

    return {
        "name": table,
        "type": obj_type,
        "database": database or conn.database,
        "schema": schema,
        "columns": columns,
        "primary_key": pk_names,
        "indexes": indexes,
        "foreign_keys": foreign_keys,
        "ddl": ddl,
    }


def _check_order_column(reflected: Table, order_by: Optional[str]) -> Optional[Column]:
    if not order_by:
        return None
    if order_by not in reflected.c:
        raise ValueError(f"排序字段不存在：{order_by}")
    return reflected.c[order_by]


def get_rows(
    conn: Connection,
    table: str,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    order_by: Optional[str] = None,
    order_dir: str = "asc",
    where: Optional[str] = None,
) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    reflected = reflect_table(engine, table, schema)

    started = time.perf_counter()
    condition = text(where) if where and where.strip() else None
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    count_stmt = select(func.count()).select_from(reflected)
    data_stmt = select(reflected)
    if condition is not None:
        count_stmt = count_stmt.where(condition)
        data_stmt = data_stmt.where(condition)

    order_column = _check_order_column(reflected, order_by)
    if order_column is not None:
        data_stmt = data_stmt.order_by(
            order_column.desc() if str(order_dir).lower() == "desc" else order_column.asc()
        )

    data_stmt = data_stmt.limit(page_size).offset((page - 1) * page_size)

    with engine.connect() as connection:
        total = connection.execute(count_stmt).scalar() or 0
        result = connection.execute(data_stmt)
        columns = [{"name": key, "type": str(reflected.c[key].type), "nullable": bool(reflected.c[key].nullable)} for key in result.keys()]
        rows = [[serialize_value(value) for value in row] for row in result.fetchall()]

    return {
        "columns": columns,
        "rows": rows,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "primary_key": [column.name for column in reflected.primary_key.columns],
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _coerce_value(column: Column, value: Any) -> Any:
    if value is None or value == "":
        return None if value is None else value
    column_type = column.type
    if isinstance(column_type, sqltypes.Boolean):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "t"}
    if isinstance(column_type, sqltypes.Integer):
        return int(value)
    if isinstance(column_type, sqltypes.Numeric) and not isinstance(column_type, sqltypes.Float):
        return Decimal(str(value))
    if isinstance(column_type, sqltypes.Float):
        return float(value)
    if isinstance(column_type, sqltypes.DateTime):
        if isinstance(value, str):
            from datetime import datetime

            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    if isinstance(column_type, sqltypes.Date):
        if isinstance(value, str):
            from datetime import date

            return date.fromisoformat(value[:10])
        return value
    if isinstance(column_type, sqltypes.Time):
        if isinstance(value, str):
            from datetime import time

            return time.fromisoformat(value)
        return value
    if isinstance(column_type, sqltypes.JSON) and isinstance(value, str):
        import json

        return json.loads(value)
    if isinstance(column_type, sqltypes.LargeBinary) and isinstance(value, str):
        if value.startswith("0x"):
            return bytes.fromhex(value[2:])
        return value.encode("utf-8")
    return value


def _pk_condition(reflected: Table, pk: Dict[str, Any]):
    if not pk:
        raise ValueError("缺少主键信息，无法定位数据行")
    clauses = []
    for name, value in pk.items():
        if name not in reflected.c:
            raise ValueError(f"主键字段不存在：{name}")
        column = reflected.c[name]
        value = _coerce_value(column, value)
        clauses.append(column.is_(None) if value is None else column == value)
    return clauses


def insert_row(
    conn: Connection,
    table: str,
    values: Dict[str, Any],
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    reflected = reflect_table(engine, table, schema)
    prepared = {
        name: _coerce_value(reflected.c[name], value)
        for name, value in values.items()
        if name in reflected.c
    }
    with engine.begin() as connection:
        result = connection.execute(reflected.insert().values(**prepared))
        affected = result.rowcount if result.rowcount and result.rowcount > 0 else 1
        inserted: Dict[str, Any] = {}
        try:
            pk_columns = list(reflected.primary_key.columns)
            for column, value in zip(pk_columns, result.inserted_primary_key):
                if value is not None:
                    inserted[column.name] = serialize_value(value)
        except Exception:
            inserted = {}
    return {"ok": True, "affected": affected, "inserted": inserted or None}


def update_row(
    conn: Connection,
    table: str,
    values: Dict[str, Any],
    pk: Dict[str, Any],
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    reflected = reflect_table(engine, table, schema)
    prepared = {
        name: _coerce_value(reflected.c[name], value)
        for name, value in values.items()
        if name in reflected.c and name not in reflected.primary_key.columns
    }
    if not prepared:
        raise ValueError("没有需要更新的字段")
    with engine.begin() as connection:
        result = connection.execute(
            reflected.update()
            .where(*_pk_condition(reflected, pk))
            .values(**prepared)
        )
        affected = result.rowcount or 0
    if affected == 0:
        raise ValueError("未找到要更新的数据行")
    return {"ok": True, "affected": affected}


def delete_row(
    conn: Connection,
    table: str,
    pk: Dict[str, Any],
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    reflected = reflect_table(engine, table, schema)
    with engine.begin() as connection:
        result = connection.execute(reflected.delete().where(*_pk_condition(reflected, pk)))
        affected = result.rowcount or 0
    if affected == 0:
        raise ValueError("未找到要删除的数据行")
    return {"ok": True, "affected": affected}


def export_query(
    conn: Connection,
    table: str,
    database: Optional[str] = None,
    schema: Optional[str] = None,
    order_by: Optional[str] = None,
    order_dir: str = "asc",
    where: Optional[str] = None,
) -> Tuple[Engine, Table, Any]:
    """Build the reflected table + SELECT statement used for CSV export."""
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    reflected = reflect_table(engine, table, schema)
    statement = select(reflected)
    if where and where.strip():
        statement = statement.where(text(where))
    order_column = _check_order_column(reflected, order_by)
    if order_column is not None:
        statement = statement.order_by(
            order_column.desc() if str(order_dir).lower() == "desc" else order_column.asc()
        )
    return engine, reflected, statement


def overview(
    conn: Connection, database: Optional[str] = None, schema: Optional[str] = None
) -> Dict[str, Any]:
    started = time.perf_counter()
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    version = server_version(engine, conn.kind)

    table_count = 0
    view_count = 0
    try:
        inspector = inspect(engine)
        table_count = len(inspector.get_table_names(schema=schema))
        view_count = len(inspector.get_view_names(schema=schema))
    except Exception:
        pass

    size = None
    pretty = None
    if conn.kind == "sqlite":
        size = sqlite_file_size(conn)
    else:
        try:
            with engine.connect() as connection:
                if conn.kind == "mysql":
                    size = connection.exec_driver_sql(
                        "SELECT SUM(data_length + index_length) FROM information_schema.tables "
                        "WHERE table_schema = DATABASE()"
                    ).scalar()
                elif conn.kind == "postgresql":
                    size = connection.exec_driver_sql(
                        "SELECT pg_database_size(current_database())"
                    ).scalar()
        except Exception:
            size = None
    if size is not None:
        size = int(size)
        pretty = size_pretty(size)

    return {
        "version": version,
        "database": database or conn.database,
        "size_bytes": size,
        "size_pretty": pretty,
        "table_count": table_count,
        "view_count": view_count,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def completion_schema(
    conn: Connection, database: Optional[str] = None, schema: Optional[str] = None
) -> Dict[str, List[str]]:
    engine = get_engine(conn, database)
    schema = _effective_schema(conn, schema)
    inspector = inspect(engine)
    result: Dict[str, List[str]] = {}
    for name in inspector.get_table_names(schema=schema)[:500]:
        try:
            result[name] = [column["name"] for column in inspector.get_columns(name, schema=schema)]
        except Exception:
            result[name] = []
    return result


def safe_error_message(exc: BaseException) -> str:
    return sanitize_error(exc)
