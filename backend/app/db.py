from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import ADMIN_DB_PATH
from .models import Base

admin_engine = create_engine(
    f"sqlite:///{ADMIN_DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)

AdminSession = sessionmaker(bind=admin_engine, autoflush=False, expire_on_commit=False)


def init_admin_db() -> None:
    Base.metadata.create_all(admin_engine)


def get_admin_db() -> Generator[Session, None, None]:
    db = AdminSession()
    try:
        yield db
    finally:
        db.close()
