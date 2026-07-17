.PHONY: help dev test lint format typecheck build up down logs health sync status deploy db-init

# VM SSH target over Tailscale. Override if your host/user differ:
#   make deploy VM=ubuntu@100.117.237.69
VM ?= ubuntu@ohlcv-prod-db

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Install dev dependencies
	uv sync
	uv run pre-commit install

test: ## Run tests
	uv run pytest

lint: ## Run linter
	uv run ruff check src/ tests/

format: ## Format code
	uv run ruff format src/ tests/

typecheck: ## Type check
	uv run ty check src/

build: ## Build Docker image
	docker compose -f docker-compose.prod.yml build

up: ## Start production stack
	docker compose -f docker-compose.prod.yml up -d

down: ## Stop production stack
	docker compose -f docker-compose.prod.yml down

logs: ## Tail scheduler logs
	docker compose -f docker-compose.prod.yml logs -f scheduler

health: ## Check system health
	docker compose -f docker-compose.prod.yml exec scheduler uv run python main.py check health

sync: ## Run manual sync
	docker compose -f docker-compose.prod.yml exec scheduler uv run python main.py sync

status: ## Show data status
	docker compose -f docker-compose.prod.yml exec scheduler uv run python main.py status

deploy: ## Pull the latest image on the VM and restart the stack (over Tailscale)
	ssh $(VM) 'cd ~/asset-price-db && docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d'

db-init: ## Initialize the QuestDB schema on the VM
	ssh $(VM) 'cd ~/asset-price-db && docker compose -f docker-compose.prod.yml exec scheduler uv run python main.py db init'
