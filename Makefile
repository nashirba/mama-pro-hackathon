.PHONY: help install db db-stop migrate seed run css messages test test-file docker-build docker-up docker-down

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Install dependencies and create .env from the example
	uv sync
	@test -f .env || cp .env.example .env

db: ## Start PostGIS in Docker (localhost:5433)
	docker compose up -d db

db-stop: ## Stop PostGIS
	docker compose stop db

migrate: ## Apply migrations
	uv run python manage.py migrate

seed: ## Load demo data (KATO, reference data, 80 specialists, 24 nannies)
	uv run python manage.py seed_demo

css: ## Build Tailwind CSS
	uv run python manage.py tailwind build

messages: ## Extract and compile translations (RU/KZ)
	uv run python manage.py makemessages -l ru -l kk --no-obsolete --ignore=.venv
	uv run python manage.py compilemessages --ignore=.venv

run: css ## Run the dev server on http://localhost:8000
	uv run python manage.py runserver

test: ## Run the full test suite (heavy)
	uv run pytest

test-file: ## Run one test file: make test-file F=tests/search/test_query.py
	uv run pytest $(F) -v

docker-build: ## Build the app image
	docker compose build web

docker-up: ## Run the app in Docker on http://localhost:8000 (migrate + seed inside)
	docker compose up -d --build web
	docker compose exec web python manage.py migrate --noinput
	docker compose exec web python manage.py seed_demo

docker-down: ## Stop all containers
	docker compose down
