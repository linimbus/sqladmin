from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import CORS_ORIGINS, FRONTEND_DIST
from .db import init_admin_db
from .routers import connections, explorer, query
from .services.connections import sanitize_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_admin_db()
    yield


app = FastAPI(
    title="SQL Station API",
    description="A lightweight multi-database SQL administration API.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connections.router, prefix="/api")
app.include_router(explorer.router, prefix="/api")
app.include_router(query.router, prefix="/api")


@app.get("/api/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": sanitize_error(exc)})


if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
