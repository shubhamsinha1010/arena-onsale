.PHONY: up down logs run test lint fmt

up:
	docker compose up -d postgres redis pgbouncer

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f postgres redis pgbouncer

run: up
	uv run uvicorn arena_onsale.api.app:app --reload --port 8000

migrate: up
	uv run alembic upgrade head

seed: migrate
	uv run python -m arena_onsale.catalog --layout small

worker: up
	uv run python -m arena_onsale.worker

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy

fmt:
	uv run ruff check --fix src tests
	uv run ruff format src tests
