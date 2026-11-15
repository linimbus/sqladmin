.PHONY: install dev backend frontend test build clean docker-build docker-run docker-up docker-down docker-seed

install:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

dev:
	./start.sh

backend:
	cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

frontend:
	cd frontend && npm run dev

test:
	cd backend && ../.venv/bin/pytest

build:
	cd frontend && npm run build

clean:
	rm -rf .venv frontend/node_modules frontend/dist backend/data .npm-cache

docker-build:
	./docker-build.sh

docker-run:
	-docker rm -f sql-station >/dev/null 2>&1
	docker run -d --name sql-station -p 8000:8000 -v sql-station-data:/app/data --restart unless-stopped sql-station:latest

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-seed:
	docker compose exec sql-station python scripts/seed_demo.py --force
