.PHONY: dev up down stop logs test lint format migrate seed worker dashboard health sync-env

# Docker Desktop uses project dir infra/ and expects infra/.env
COMPOSE=docker compose -f infra/docker-compose.yml --env-file infra/.env -p leadintel

sync-env:
	@if not exist .env copy .env.example .env
	@copy /Y .env infra\.env >nul

dev: up

up: sync-env
	$(COMPOSE) up -d --build

stop: sync-env
	$(COMPOSE) stop

down: sync-env
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

migrate:
	$(COMPOSE) exec api alembic upgrade head

seed:
	$(COMPOSE) exec api python -m app.scripts.seed

test:
	cd apps/api && python -m pytest -q

lint:
	cd apps/api && ruff check app tests
	cd apps/api && mypy app || true

format:
	cd apps/api && ruff format app tests

worker:
	$(COMPOSE) logs -f workers

dashboard:
	$(COMPOSE) logs -f dashboard

health:
	curl -sS http://localhost:8000/healthz

odoo-package:
	bash scripts/odoo-package.sh
