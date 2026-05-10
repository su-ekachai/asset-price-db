.PHONY: help dev test lint format typecheck build up down logs health sync status

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

logs: ## Tail app logs
	docker compose -f docker-compose.prod.yml logs -f app scheduler

health: ## Check system health
	docker compose -f docker-compose.prod.yml exec app uv run python main.py check health

sync: ## Run manual sync
	docker compose -f docker-compose.prod.yml exec app uv run python main.py sync

status: ## Show data status
	docker compose -f docker-compose.prod.yml exec app uv run python main.py status
