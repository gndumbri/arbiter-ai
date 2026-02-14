.PHONY: dev test lint migrate up down

# Start Docker services
up:
	docker compose up -d

# Stop Docker services
down:
	docker compose down

# Run database migrations
migrate:
	cd backend && uv run alembic upgrade head

# Run all backend tests
test:
	cd backend && uv run pytest tests/ -v

# Run linters
lint:
	cd backend && uv run ruff check app/
	cd backend && uv run mypy app/ --ignore-missing-imports

# Start backend dev server
backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# Start frontend dev server
frontend:
	cd frontend && npm run dev

# Start everything (requires tmux or multiple terminals)
dev: up
	@echo "Docker services started. Run 'make backend' and 'make frontend' in separate terminals."
