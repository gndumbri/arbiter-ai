# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Mandatory Quality Rules

**Before completing ANY task in this repo, you MUST follow these workflows:**

1. **Every code change** → follow `.agent/workflows/testing.md` (write tests, run the suite)
2. **Every feature/endpoint/schema change** → follow `.agent/workflows/update-prd.md` (update plan.md and specs)
3. **Every frontend component** → follow `.agent/workflows/accessibility.md` (WCAG 2.1 AA compliance)
4. **Every feature completion** → follow `.agent/workflows/end-to-end.md` (verify full-stack connectivity)
5. **Before any commit** → run `.agent/workflows/quality-gate.md` (the 5-gate checklist)

These are NOT optional. A feature is not done until all 5 quality gates pass.

## Build & Development Commands

### Makefile shortcuts (preferred)

- `make up` — Start Docker services (Postgres, Redis)
- `make down` — Stop Docker services
- `make migrate` — Run DB migrations
- `make test` — Run backend tests
- `make lint` — Run ruff + mypy
- `make backend` — Start backend dev server (port 8000)
- `make frontend` — Start frontend dev server (port 3000)
- `make dev` — Start Docker + print instructions for backend/frontend

### Manual commands

- `docker compose up -d` — Start Postgres and Redis
- `cd backend && uv sync` — Install Python deps
- `cd backend && uv run alembic upgrade head` — Run DB migrations
- `cd backend && uv run uvicorn app.main:app --reload --port 8000` — Start API
- `cd backend && uv run celery -A app.workers.tasks worker --loglevel=info` — Start Celery worker (not yet implemented)
- `cd frontend && npm install` — Install frontend deps
- `cd frontend && npm run dev` — Start Next.js dev server
- `cd backend && uv run pytest tests/ -v` — Run backend tests
- `cd backend && uv run ruff check app/` — Lint Python
- `cd backend && uv run mypy app/ --ignore-missing-imports` — Type check Python

## Architecture

- **Backend:** Python 3.12+ / FastAPI — `backend/app/`
- **Frontend:** Next.js 16 / React 19 (TypeScript) — `frontend/src/`
- **Vector DB:** Pinecone Serverless (namespace-per-tenant)
- **Relational DB:** PostgreSQL 16 (via Docker locally, Supabase in prod)
- **Queue:** Redis 7 + Celery (async ingestion, not yet implemented)
- **Auth:** Supabase Auth (JWT) — stub in `api/deps.py`, integration pending
- **Billing:** Stripe (not yet implemented)
- **Migrations:** Alembic — `backend/alembic/`

## Key Documentation

- `plan.md` — Comprehensive technical spec (architecture, API, data models, implementation checklist)
- `prd.md` — Product requirements (personas, feature maps, success metrics)
- `spec.md` — Technical specification (stack, schemas, security, performance targets)

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory (lifespan, CORS, middleware)
│   │   ├── config.py            # Pydantic Settings (all env vars)
│   │   ├── api/
│   │   │   ├── deps.py          # Dependency injection (DB, Redis, Auth)
│   │   │   ├── middleware.py    # RequestID, Logging, Error handling
│   │   │   └── routes/          # health.py, sessions.py
│   │   ├── models/
│   │   │   ├── tables.py       # SQLAlchemy ORM (8 tables)
│   │   │   ├── schemas.py      # Pydantic request/response schemas
│   │   │   └── database.py     # Async engine + session factory
│   │   ├── core/                # Ingestion, retrieval, judge (not yet implemented)
│   │   ├── db/                  # Query helpers (not yet implemented)
│   │   └── workers/             # Celery tasks (not yet implemented)
│   ├── alembic/                 # DB migrations (initial schema complete)
│   └── tests/unit/              # test_health.py, test_schemas.py, test_config.py
├── frontend/
│   └── src/
│       ├── app/                 # Next.js App Router (layout.tsx, page.tsx)
│       ├── lib/
│       │   ├── api.ts           # API client (health, sessions, judge endpoints)
│       │   └── types.ts         # TypeScript interfaces matching backend schemas
│       └── components/          # UI components (not yet implemented)
├── .agent/workflows/            # 9 quality workflow files
├── docker-compose.yml           # Postgres 16 + Redis 7
├── Makefile                     # Dev command shortcuts
└── .env.example                 # Environment variable template
```

## Implementation Status

| Component | Status | Details |
|-----------|--------|---------|
| DB schema & migrations | ✅ Done | 8 tables, initial Alembic migration |
| FastAPI scaffolding | ✅ Done | App factory, middleware, config, deps |
| Health endpoint | ✅ Done | `GET /health` with DB/Redis checks |
| Sessions endpoint | ✅ Done | `POST /api/v1/sessions` |
| Frontend scaffolding | ✅ Done | Next.js 16 app, API client, TypeScript types |
| Backend tests | 🟡 Partial | Health, schemas, config — needs expansion |
| Auth (Supabase JWT) | 🟡 Stub | JWT parsing in deps.py, needs Supabase wiring |
| Ingestion pipeline | ❌ Not started | PDF parsing, virus scan, chunking, indexing |
| Adjudication engine | ❌ Not started | Retrieval, reranking, LLM judge |
| Frontend components | ❌ Not started | Chat, file upload, citations, library |
| Stripe billing | ❌ Not started | Checkout, webhooks, portal |
| Publisher API | ❌ Not started | API-key auth, official ruleset management |
| Celery workers | ❌ Not started | Async task definitions |
| PWA setup | ❌ Not started | Manifest, service worker, offline page |
| Frontend tests | ❌ Not started | No test framework configured yet |

## Database Tables (8)

`users`, `sessions`, `ruleset_metadata`, `publishers`, `official_rulesets`, `user_game_library`, `file_blocklist`, `query_audit_log`

See `backend/app/models/tables.py` for full ORM definitions.
