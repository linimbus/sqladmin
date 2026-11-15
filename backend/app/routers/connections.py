from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import encrypt
from ..db import get_admin_db
from ..deps import load_connection
from ..models import Connection
from ..schemas import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionTest,
    ConnectionUpdate,
    TestResult,
)
from ..services.connections import (
    DEFAULT_PORTS as SERVICE_PORTS,
    dispose_connection,
    ensure_sqlite_file,
    test_connection,
)

router = APIRouter(prefix="/connections", tags=["connections"])


def to_out(connection: Connection) -> ConnectionOut:
    return ConnectionOut(
        id=connection.id,
        name=connection.name,
        kind=connection.kind,
        host=connection.host,
        port=connection.port,
        username=connection.username,
        database=connection.database,
        sqlite_path=connection.sqlite_path,
        options=connection.options or {},
        read_only=bool(connection.read_only),
        has_password=bool(connection.password_enc),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _ensure_unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    existing = db.execute(select(Connection).where(Connection.name == name)).scalar_one_or_none()
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(status_code=409, detail=f"连接名称「{name}」已存在")


def _prepare_saved(connection: Connection) -> None:
    if connection.kind == "sqlite":
        connection.sqlite_path = ensure_sqlite_file(connection.sqlite_path)
        connection.host = None
        connection.port = None
        connection.username = None
        connection.database = None
    else:
        connection.port = connection.port or SERVICE_PORTS.get(connection.kind)
        connection.host = (connection.host or "127.0.0.1").strip()
        connection.sqlite_path = None
        if not (connection.database or "").strip():
            connection.database = None


@router.get("", response_model=List[ConnectionOut])
def list_connections(db: Session = Depends(get_admin_db)) -> List[ConnectionOut]:
    connections = db.execute(select(Connection).order_by(Connection.id)).scalars().all()
    return [to_out(connection) for connection in connections]


@router.post("", response_model=ConnectionOut, status_code=201)
def create_connection(
    payload: ConnectionCreate, db: Session = Depends(get_admin_db)
) -> ConnectionOut:
    _ensure_unique_name(db, payload.name)
    connection = Connection(
        name=payload.name,
        kind=payload.kind,
        host=payload.host,
        port=payload.port or SERVICE_PORTS.get(payload.kind),
        username=payload.username,
        password_enc=encrypt(payload.password) if payload.password else None,
        database=payload.database,
        sqlite_path=payload.sqlite_path,
        options=payload.options or {},
        read_only=payload.read_only,
    )
    try:
        _prepare_saved(connection)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(connection)
    db.commit()
    db.refresh(connection)
    return to_out(connection)


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(connection: Connection = Depends(load_connection)) -> ConnectionOut:
    return to_out(connection)


@router.put("/{connection_id}", response_model=ConnectionOut)
def update_connection(
    payload: ConnectionUpdate,
    connection: Connection = Depends(load_connection),
    db: Session = Depends(get_admin_db),
) -> ConnectionOut:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="连接名称不能为空")
        _ensure_unique_name(db, name, exclude_id=connection.id)
        data["name"] = name

    password = data.pop("password", None)
    if password:
        connection.password_enc = encrypt(password)

    for field, value in data.items():
        setattr(connection, field, value)

    if connection.kind == "sqlite":
        connection.host = None
        connection.port = None
        connection.username = None
        connection.database = None
    else:
        connection.sqlite_path = None
        connection.port = connection.port or SERVICE_PORTS.get(connection.kind)
        connection.host = (connection.host or "127.0.0.1").strip()

    try:
        if connection.kind == "sqlite":
            connection.sqlite_path = ensure_sqlite_file(connection.sqlite_path)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dispose_connection(connection.id)
    db.commit()
    db.refresh(connection)
    return to_out(connection)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(
    connection: Connection = Depends(load_connection),
    db: Session = Depends(get_admin_db),
) -> None:
    dispose_connection(connection.id)
    db.delete(connection)
    db.commit()


@router.post("/test", response_model=TestResult)
def test_connection_config(payload: ConnectionTest) -> TestResult:
    password_enc = encrypt(payload.password) if payload.password else None
    sqlite_path = payload.sqlite_path
    if payload.id:
        from ..db import AdminSession

        with AdminSession() as db:
            saved = db.get(Connection, payload.id)
            if saved is None:
                raise HTTPException(status_code=404, detail="连接不存在或已被删除")
            if not password_enc:
                password_enc = saved.password_enc
            if not sqlite_path and saved.kind == payload.kind:
                sqlite_path = saved.sqlite_path

    transient = Connection(
        name=payload.name,
        kind=payload.kind,
        host=payload.host,
        port=payload.port or SERVICE_PORTS.get(payload.kind),
        username=payload.username,
        password_enc=password_enc,
        database=payload.database,
        sqlite_path=sqlite_path,
        options=payload.options or {},
        read_only=payload.read_only,
    )
    if transient.kind == "sqlite" and not transient.sqlite_path:
        raise HTTPException(status_code=400, detail="请填写 SQLite 数据库文件路径")

    result = test_connection(transient)
    if not result["ok"]:
        # A driver that is not installed gets a clearer hint.
        message = result["message"]
        if "No module named" in message:
            driver = {
                "mysql": "pymysql",
                "postgresql": "pg8000",
                "mssql": "pymssql",
                "oracle": "oracledb",
            }.get(payload.kind)
            message = f"缺少驱动，请先安装：pip install {driver}（{message}）"
        return TestResult(ok=False, message=message, latency_ms=result["latency_ms"])
    return TestResult(**result)
