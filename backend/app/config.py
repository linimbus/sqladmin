from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Load a simple KEY=VALUE .env file without extra dependencies."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("SQL_ADMIN_DATA_DIR", str(BASE_DIR / "data"))).expanduser()
DATA_DIR = DATA_DIR.resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_DB_PATH = DATA_DIR / "admin.db"
SECRET_KEY_PATH = DATA_DIR / "secret.key"

MAX_ROWS_LIMIT = int(os.getenv("SQL_ADMIN_MAX_ROWS_LIMIT", "5000"))
MAX_PAGE_SIZE = int(os.getenv("SQL_ADMIN_MAX_PAGE_SIZE", "500"))

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "SQL_ADMIN_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

FRONTEND_DIST = Path(
    os.getenv("SQL_ADMIN_FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist"))
).resolve()
