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

- `docker compose up -d` — Start Postgres, Redis, ClamAV
- `cd backend && uv sync` — Install Python deps
- `cd backend && alembic upgrade head` — Run DB migrations
- `cd backend && uvicorn app.main:app --reload --port 8000` — Start API
- `cd backend && celery -A app.workers.tasks worker --loglevel=info` — Start worker
- `cd frontend && npm install` — Install frontend deps
- `cd frontend && npm run dev` — Start Next.js on port 3000
- `cd backend && python -m pytest tests/ -v` — Run backend tests
- `cd frontend && npm test` — Run frontend tests
- `cd backend && ruff check app/` — Lint Python

## Architecture

- **Backend:** Python 3.12+ / FastAPI — `backend/app/`
- **Frontend:** Next.js 14+ (PWA) — `frontend/src/`
- **Vector DB:** Pinecone Serverless (namespace-per-tenant)
- **Relational DB:** PostgreSQL via Supabase
- **Queue:** Redis + Celery (async ingestion)
- **Auth:** Supabase Auth (JWT)
- **Billing:** Stripe
- **PRD:** See `plan.md` for complete technical spec
