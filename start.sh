#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "==> 创建 Python 虚拟环境"
  python3 -m venv .venv
fi

echo "==> 安装后端依赖"
.venv/bin/pip install -q -r backend/requirements.txt

if [ ! -d "frontend/node_modules" ]; then
  echo "==> 安装前端依赖"
  (cd frontend && npm install)
fi

cleanup() {
  echo ""
  echo "==> 正在停止服务"
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> 启动后端 http://127.0.0.1:8000"
(cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
BACKEND_PID=$!

echo "==> 启动前端 http://127.0.0.1:5173"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

wait
