from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from ..config import DATA_DIR
from ..crypto import decrypt
from ..models import Connection

DEFAULT_PORTS = {
    "mysql": 3306,
    "postgresql": 5432,
    "mssql": 1433,
    "oracle": 1521,
}

_engines: Dict[tuple, Engine] = {}
_lock = threading.RLock()


def resolve_sqlite_path(raw_path: Optional[str]) -> str:
    """Resolve a user supplied SQLite path. Relative paths live under DATA_DIR."""
    if not raw_path or not raw_path.strip():
        raise ValueError("请填写 SQLite 数据库文件路径")
    raw = raw_path.strip()
    if raw == ":memory:":
        return raw
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = DATA_DIR / path
    return str(path.resolve())


def ensure_sqlite_file(raw_path: Optional[str]) -> str:
    path = resolve_sqlite_path(raw_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(path).exists():
            Path(path).touch()
    return path


def build_url(conn: Connection, database: Optional[str] = None) -> URL:
    kind = conn.kind
    if kind == "sqlite":
        path = resolve_sqlite_path(conn.sqlite_path)
        return URL.create("sqlite", database=path)

    db_name = (database or conn.database or "").strip() or None
    host = (conn.host or "127.0.0.1").strip()
    port = conn.port or DEFAULT_PORTS.get(kind)

    if kind == "mysql":
        query: Dict[str, str] = {"charset": str((conn.options or {}).get("charset") or "utf8mb4")}
        query["connect_timeout"] = "10"
        return URL.create(
            "mysql+pymysql",
            username=conn.username or None,
            password=decrypt(conn.password_enc or "") or None,
            host=host,
            port=port,
            database=db_name,
            query=query,
        )

    if kind == "postgresql":
        return URL.create(
            "postgresql+pg8000",
            username=conn.username or None,
            password=decrypt(conn.password_enc or "") or None,
            host=host,
            port=port,
            database=db_name,
        )

    if kind == "mssql":
        return URL.create(
            "mssql+pymssql",
            username=conn.username or None,
            password=decrypt(conn.password_enc or "") or None,
            host=host,
            port=port,
            database=db_name,
        )

    if kind == "oracle":
        return URL.create(
            "oracle+oracledb",
            username=conn.username or None,
            password=decrypt(conn.password_enc or "") or None,
            host=host,
            port=port,
            database=db_name,
        )

    raise ValueError(f"暂不支持的数据库类型：{kind}")


def _engine_kwargs(conn: Connection) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"pool_pre_ping": True, "pool_recycle": 1800}
    if conn.kind == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 20}
    elif conn.kind == "postgresql":
        kwargs["connect_args"] = {"timeout": 10}
    elif conn.kind == "mssql":
        kwargs["connect_args"] = {"login_timeout": 10}
    return kwargs


def get_engine(conn: Connection, database: Optional[str] = None) -> Engine:
    """Return a cached engine, optionally bound to another database/catalog."""
    catalog = None
    if database and conn.kind in ("mysql", "postgresql", "mssql"):
        catalog = database
    key = (conn.id, catalog)
    with _lock:
        engine = _engines.get(key)
        if engine is None:
            engine = create_engine(build_url(conn, catalog), **_engine_kwargs(conn))
            _engines[key] = engine
        return engine


def dispose_connection(conn_id: int) -> None:
    with _lock:
        for key in [k for k in _engines if k[0] == conn_id]:
            try:
                _engines.pop(key).dispose()
            except Exception:
                pass


def _create_ephemeral_engine(conn: Connection, database: Optional[str] = None) -> Engine:
    kwargs = _engine_kwargs(conn)
    kwargs["poolclass"] = NullPool
    return create_engine(build_url(conn, database), **kwargs)


def sanitize_error(exc: BaseException) -> str:
    message = str(getattr(exc, "orig", None) or exc)
    message = re.sub(r"(://[^:/@\s]+:)([^@\s]+)(@)", r"\1***\3", message)
    message = re.sub(r"(password=)[^\s;&]+", r"\1***", message, flags=re.IGNORECASE)
    return message.strip()[:2000]


def server_version(engine: Engine, kind: str) -> Optional[str]:
    statements = {
        "sqlite": "SELECT sqlite_version()",
        "mysql": "SELECT VERSION()",
        "postgresql": "SHOW server_version",
        "mssql": "SELECT CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(64))",
        "oracle": "SELECT version FROM product_component_version WHERE product LIKE 'Oracle Database%'",
    }
    sql = statements.get(kind)
    if not sql:
        return None
    try:
        with engine.connect() as connection:
            return str(connection.exec_driver_sql(sql).scalar())
    except Exception:
        return None


def test_connection(conn: Connection, database: Optional[str] = None) -> Dict[str, Any]:
    started = time.perf_counter()
    engine = None
    try:
        if conn.kind == "sqlite":
            ensure_sqlite_file(conn.sqlite_path)
        engine = _create_ephemeral_engine(conn, database)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            version = server_version(engine, conn.kind)
        latency = round((time.perf_counter() - started) * 1000, 1)
        label = f"连接成功（{latency} ms）"
        if version:
            label += f"，服务端版本 {version}"
        return {"ok": True, "message": label, "version": version, "latency_ms": latency}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "message": sanitize_error(exc),
            "version": None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass


def apply_schema(connection, kind: str, schema: Optional[str]) -> None:
    """Set PostgreSQL search_path for this session."""
    if not schema:
        return
    if kind == "postgresql":
        quoted = '"' + schema.replace('"', '""') + '"'
        connection.exec_driver_sql(f"SET search_path TO {quoted}")


def connection_preview(conn: Connection) -> str:
    if conn.kind == "sqlite":
        return conn.sqlite_path or ""
    host = conn.host or "127.0.0.1"
    port = conn.port or DEFAULT_PORTS.get(conn.kind, "")
    db = conn.database or ""
    return f"{host}:{port}/{db}"


def quote_identifier(engine: Engine, name: str) -> str:
    return engine.dialect.identifier_preparer.quote(name)


def size_pretty(size: Optional[int]) -> Optional[str]:
    if size is None:
        return None
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return None


def sqlite_file_size(conn: Connection) -> Optional[int]:
    try:
        path = resolve_sqlite_path(conn.sqlite_path)
        if path == ":memory:":
            return None
        return os.path.getsize(path)
    except OSError:
        return None


def is_driver_missing(exc: BaseException) -> bool:
    return isinstance(exc, (ModuleNotFoundError, ImportError)) or "No module named" in str(exc)
