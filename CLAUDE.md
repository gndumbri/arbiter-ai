# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Mandatory Quality Rules

**Before completing ANY task in this repo, you MUST follow these workflows:**

1. **Every code change** → follow `.agent/workflows/testing.md` (write tests, run the suite)
2. **Every feature/endpoint/schema change** → follow `.agent/workflows/update-prd.md` (update plan.md and specs)
3. **Every frontend component** → follow `.agent/workflows/accessibility.md` (WCAG 2.1 AA compliance)
4. **Every feature completion** → follow `.agent/workflows/end-to-end.md` (verify full-stack connectivity)
5. **Before any commit** → run `.agent/workflows/quality-gate.md` (the 5-gate checklist)
6. **Every code change** → follow `.agent/workflows/commenting.md` (clear docstrings, WHY-comments, no stale comments)

These are NOT optional. A feature is not done until all quality gates pass.

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

## Dependency & Docker Build Sync

When `frontend/package.json` or `frontend/package-lock.json` change (adding, removing, or upgrading dependencies), you **must** verify the container build is not broken:

1. **Node version must match.** The `node:XX-alpine` base image in `frontend/Dockerfile` must use the same **major** Node version as the local dev environment (currently Node 25 / npm 11). A mismatch causes `npm ci` to fail or produce a different dependency tree. Check with `node --version` locally and compare to the `FROM` lines in `frontend/Dockerfile`.
2. **Always run `npm install` locally first** to regenerate `package-lock.json`, then commit both `package.json` and `package-lock.json` together.
3. **`npm ci` in Docker.** The frontend Dockerfile uses `npm ci` (not `npm install`) for deterministic builds from the lockfile. If `npm ci` fails in Docker but `npm install` works locally, the most common cause is a Node/npm version mismatch between the Dockerfile base image and your local environment.
4. **`.npmrc` must be present.** `frontend/.npmrc` sets `legacy-peer-deps=true` so both local dev and Docker behave consistently without CLI flags. Do not remove it.
5. **Backend deps (Python/uv).** The backend Dockerfile uses `uv sync --frozen` against `pyproject.toml` / `uv.lock`. After changing Python dependencies, run `uv lock` locally and commit `uv.lock`.

**Checklist after any dependency change:**
- [ ] `package-lock.json` (or `uv.lock`) is updated and committed
- [ ] Dockerfile base image Node (or Python) version still matches local
- [ ] `docker compose build frontend` (or `backend`) succeeds
- [ ] App starts correctly in the container

### Build Readiness Check

**Every time code changes are detected in `frontend/` or `backend/`, you MUST perform a build readiness check before considering the task complete.** This applies to all changes — not just dependency updates.

**Frontend (`frontend/`) — verify all of the following:**
1. Every `import` in changed/new files resolves to a package in `package.json` or a local file that exists
2. All referenced local components (`@/components/`, `@/hooks/`, `@/lib/`) exist
3. `next.config.ts` still has `output: "standalone"` (required for Docker)
4. `node:XX-alpine` in `frontend/Dockerfile` matches local Node major version
5. `package-lock.json` lockfile version is compatible with the npm version in the Dockerfile

**Backend (`backend/`) — verify all of the following:**
1. Every `import` in changed/new files resolves to a package in `pyproject.toml` or a local module that exists
2. New routes are registered in `app/main.py` via `app.include_router()`
3. New modules have `__init__.py` files in their directories
4. `uv.lock` is present and up to date
5. `python:XX-slim` in `backend/Dockerfile` matches the required Python version in `pyproject.toml`

**If any check fails, fix the issue before proceeding.**

## Architecture

- **Backend:** Python 3.12+ / FastAPI — `backend/app/`
- **Frontend:** Next.js 16 / React 19 (TypeScript, PWA) — `frontend/src/`
- **Provider Abstraction:** Protocol-based interfaces in `app/core/protocols.py` — swap any provider via config
- **Vector DB:** Pinecone Serverless (namespace-per-ruleset)
- **Relational DB:** PostgreSQL 16 (Docker locally, RDS in prod)
- **Queue:** Redis 7 + Celery (async ingestion)
- **Auth:** NextAuth.js (JWT strategy) — validated in `api/deps.py`
- **Billing:** Stripe Checkout + Webhooks — `api/routes/billing.py`
- **LLM:** OpenAI (default), Anthropic (alt) — swappable via config
- **Migrations:** Alembic — `backend/alembic/`
- **PRD:** See `plan.md` / `prd.md` / `spec.md`

## Key Documentation

- `plan.md` — Comprehensive technical spec (architecture, API, data models, implementation checklist)
- `prd.md` — Product requirements (personas, feature maps, success metrics)
- `spec.md` — Technical specification (stack, schemas, security, performance targets)

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app factory
│   │   ├── config.py         # Pydantic Settings (all env vars)
│   │   ├── api/
│   │   │   ├── deps.py       # Auth (NextAuth JWT), DB, Redis injection
│   │   │   ├── middleware.py  # RequestID, logging, error handling
│   │   │   └── routes/       # 12 route modules (43 endpoints)
│   │   ├── models/
│   │   │   ├── tables.py     # SQLAlchemy ORM (10 tables)
│   │   │   ├── schemas.py    # Pydantic request/response schemas
│   │   │   └── database.py   # Async engine + session factory
│   │   └── core/             # Ingestion, retrieval, judge engine
│   ├── alembic/              # DB migrations
│   ├── Dockerfile            # Multi-stage Python build
│   └── tests/                # pytest suite (31 tests)
├── frontend/
│   ├── Dockerfile            # Multi-stage Next.js build
│   └── src/
│       ├── app/              # App Router (14 routes)
│       ├── lib/api.ts        # Typed API client (30 methods)
│       └── components/       # Shadcn UI components
├── docs/aws-deployment.md    # AWS deployment guide
├── docker-compose.yml        # Full-stack Docker setup
├── Makefile                  # Dev command shortcuts
└── .env.example              # Environment variable template
```

## Implementation Status

| Component              | Status         | Details                                        |
| ---------------------- | -------------- | ---------------------------------------------- |
| DB schema & migrations | ✅ Done        | 10 tables, Alembic migrations                  |
| FastAPI scaffolding    | ✅ Done        | App factory, middleware, config, deps          |
| Auth (NextAuth JWT)    | ✅ Done        | JWT validation in `deps.py`, user upsert       |
| Stripe billing         | ✅ Done        | Checkout, webhooks, 3 lifecycle handlers       |
| Publisher API          | ✅ Done        | SHA-256 API key auth, key rotation             |
| User library           | ✅ Done        | 5 CRUD endpoints                               |
| User profile           | ✅ Done        | GET/PATCH/DELETE `/users/me`                   |
| Catalog API            | ✅ Done        | List + detail endpoints                        |
| Sessions API           | ✅ Done        | CRUD + active_only filter                      |
| Judge API              | ✅ Done        | RAG adjudication with tier-based rate limiting |
| Frontend (14 routes)   | ✅ Done        | Dashboard, catalog, settings, widget, auth     |
| API client (`api.ts`)  | ✅ Done        | 30 typed methods with auto Bearer token        |
| PWA setup              | ✅ Done        | Manifest, service worker, offline page         |
| Backend tests          | ✅ Done        | 31 tests (routes + unit)                       |
| Ingestion pipeline     | 🟡 Partial     | Chunking done, full pipeline in progress       |
| Celery workers         | 🟡 Stub        | Task definitions, needs full wiring            |
| Frontend tests         | ❌ Not started | No test framework configured yet               |

## Database Tables (10)

`users`, `sessions`, `ruleset_metadata`, `publishers`, `official_rulesets`, `user_game_library`, `file_blocklist`, `query_audit_log`, `subscriptions`, `subscription_tiers`

See `backend/app/models/tables.py` for full ORM definitions.
