# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# 1) Build the Vue frontend
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# 2) Python runtime + FastAPI + built frontend
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ARG INSTALL_MSSQL=false
ARG INSTALL_ORACLE=false

LABEL org.opencontainers.image.title="SQL Station" \
      org.opencontainers.image.description="Multi-database SQL administration workbench" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SQL_ADMIN_DATA_DIR=/app/data \
    SQL_ADMIN_FRONTEND_DIST=/app/frontend/dist

WORKDIR /app

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app --no-create-home app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && if [ "$INSTALL_MSSQL" = "true" ]; then pip install --no-cache-dir pymssql; fi \
    && if [ "$INSTALL_ORACLE" = "true" ]; then pip install --no-cache-dir oracledb; fi

COPY --chown=app:app backend/ /app/backend/
COPY --from=frontend-build --chown=app:app /build/frontend/dist /app/frontend/dist

RUN mkdir -p /app/data && chown -R app:app /app/data

USER app
WORKDIR /app/backend

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
