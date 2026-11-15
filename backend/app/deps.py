from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_admin_db
from .models import Connection


def load_connection(
    connection_id: int, db: Session = Depends(get_admin_db)
) -> Connection:
    connection = db.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="连接不存在或已被删除")
    return connection


def ensure_writable(connection: Connection) -> None:
    if connection.read_only:
        raise HTTPException(status_code=403, detail="当前连接处于只读模式，禁止修改数据")
