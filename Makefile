.PHONY: help up down logs build ingest seed test lint clean dev-api dev-web

help:
	@echo "make up       - build and start everything (db, api, web)"
	@echo "make ingest   - run the pipeline now and populate the digest"
	@echo "make test     - run the backend test suite"
	@echo "make logs     - follow the api logs"
	@echo "make down     - stop everything"
	@echo "make clean    - stop and delete volumes (data and cache)"

up:
	docker compose up --build -d
	@echo "api  http://localhost:8000/docs"
	@echo "web  http://localhost:3000"
	@echo "run 'make ingest' to populate the digest"

build:
	docker compose build

down:
	docker compose down

clean:
	docker compose down -v

logs:
	docker compose logs -f api

ingest:
	docker compose exec api python -m app.cli ingest

seed:
	docker compose exec api python -m app.cli seed

test:
	cd backend && DATABASE_URL="sqlite+pysqlite:///./test.db" DATA_MODE=seed \
		LLM_PROVIDER=null SCHEDULER_ENABLED=false python -m pytest tests -q

dev-api:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-web:
	cd web && npm run dev
