.PHONY: dev test test-backend test-frontend lint lint-backend lint-frontend migrate up down

# Start Docker services
up:
	docker compose up -d

# Stop Docker services
down:
	docker compose down

# Run database migrations
migrate:
	cd backend && uv run alembic upgrade head

# Run backend tests only
test-backend:
	cd backend && uv run pytest tests/ -v

# Run frontend tests only
test-frontend:
	cd frontend && npm run test

# Run backend + frontend tests
test: test-backend test-frontend

# Run backend linters only
lint-backend:
	cd backend && uv run ruff check app/ tests
	cd backend && uv run --with mypy mypy app/config.py app/core/environment.py --ignore-missing-imports

# Run frontend linter only
lint-frontend:
	cd frontend && npm run lint

# Run backend + frontend linters
lint: lint-backend lint-frontend

# Start backend dev server
backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# Start frontend dev server
frontend:
	cd frontend && npm run dev

# Start everything (requires tmux or multiple terminals)
dev: up
	@echo "Docker services started. Run 'make backend' and 'make frontend' in separate terminals."
