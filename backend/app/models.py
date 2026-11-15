from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Connection(Base):
    """A saved database connection (metadata only, in the local admin SQLite DB)."""

    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)

    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    database: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sqlite_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    options: Mapped[dict] = mapped_column(JSON, default=dict)
    read_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
