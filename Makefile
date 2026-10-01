# ============================================================
# SolarShare — developer task runner
#
# Docker note: `docker compose up -d` does NOT rebuild images.
# If you change source you must rebuild, otherwise you silently
# keep running the previous image. Always use `make up` (or pass
# `--build`) instead of bare `docker compose up -d`.
# ============================================================

COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: help up down restart rebuild logs ps shell seed ingest train \
        profiles test lint build dev-api dev-ui clean nuke

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ─── Docker ───────────────────────────────────────────────
up: ## Build (if needed) + start the full stack  ← use this, not bare `up -d`
	$(COMPOSE) up -d --build
	@echo "→ http://localhost  (admin: ADMIN / 4005)"

down: ## Stop the stack (keeps the DB volume)
	$(COMPOSE) down

restart: ## Restart containers without rebuilding
	$(COMPOSE) restart

rebuild: ## Force a clean rebuild of both images, then start
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

logs: ## Tail all container logs
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

shell: ## Open a shell in the backend container
	$(COMPOSE) exec backend /bin/bash

clean: ## Stop stack and delete the database volume (DESTROYS DATA)
	$(COMPOSE) down -v

nuke: ## Remove containers, volumes and built images
	$(COMPOSE) down -v --rmi all

# ─── Data ─────────────────────────────────────────────────
seed: ## Seed demo estate / tenants / users (idempotent)
	$(COMPOSE) exec backend python scripts/seed_demo.py

train: ## Re-train + re-serialise the 6 tenant Prophet models
	$(COMPOSE) exec backend python scripts/train_tenant_models.py

ingest: ## Ingest the mounted Zenodo .tsf dataset into the container DB
	$(COMPOSE) exec backend python -c "from app.db.session import SessionLocal; \
from app.db.init_db import init_db; \
from app.services.electricity_ingestion import ingest_electricity_dataset; \
init_db(); db = SessionLocal(); \
print(ingest_electricity_dataset(db, local_path='/app/data/electricity_hourly_dataset.tsf'))"

profiles: ## Run the 321→6 load-profile selection against the container DB
	$(COMPOSE) exec backend python -c "from app.db.session import SessionLocal; \
from app.services.load_profiling import run_profiling_pipeline; import json; \
db = SessionLocal(); print(json.dumps(run_profiling_pipeline(db, persist=True), indent=2, default=str))"

# ─── Local development (no Docker) ────────────────────────
dev-api: ## Run FastAPI locally on :8000 with reload
	python -m uvicorn app.main:app --reload --port 8000

dev-ui: ## Run the Vite dev server on :3000 (proxies /api to :8000)
	npm run dev

test: ## Run the pytest suite
	python -m pytest -q

lint: ## Type-check the frontend
	npx tsc --noEmit

build: ## Type-check + build the frontend bundle
	npm run build