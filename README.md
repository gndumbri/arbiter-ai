# Arbiter AI

**The AI-powered rules judge for tabletop gaming.** Upload your game's rulebook, ask questions in natural language, and get cited verdicts backed by RAG (Retrieval-Augmented Generation).

## Architecture

```mermaid
graph LR
    subgraph Frontend
        A[Next.js 16 PWA<br/>port 3000]
    end
    subgraph Backend
        B[FastAPI<br/>port 8000]
        C[Celery Worker]
        F[Celery Beat]
    end
    subgraph Data
        D[(PostgreSQL 16<br/>+ pgvector)]
        E[(Redis 7)]
    end
    subgraph External
        G[AWS Bedrock<br/>Claude + Titan]
        H[Stripe]
        I[NextAuth]
    end

    A -->|REST API| B
    B --> D
    B --> E
    C --> E
    C --> D
    F --> E
    B --> G
    B --> H
    A --> I
```

| Layer         | Tech                                | Purpose                              |
| ------------- | ----------------------------------- | ------------------------------------ |
| Frontend      | Next.js 16, React 19, TypeScript    | PWA with App Router                  |
| Backend       | FastAPI, Python 3.14+, SQLAlchemy 2 | REST API + async workers             |
| Auth          | NextAuth.js v5 (JWT strategy)       | Session management + JWT validation  |
| Billing       | Stripe Checkout + Webhooks          | PRO tier subscriptions               |
| Vector DB     | pgvector (PostgreSQL extension)     | Namespace-per-ruleset embeddings     |
| Relational DB | PostgreSQL 16                       | Users, sessions, rulesets, audit log |
| Queue         | Redis 7 + Celery Worker + Beat      | Async ingestion + scheduled syncs    |
| LLM           | AWS Bedrock (Claude 3.5 Sonnet)     | RAG adjudication engine              |
| Embeddings    | AWS Bedrock (Titan Embed v2)        | Document + query embeddings          |
| Reranker      | FlashRank (local, no API key)       | Retrieval result reranking           |

## Prerequisites

- **Node.js** 20+ and npm
- **Python** 3.14+ and [uv](https://docs.astral.sh/uv/)
- **Docker** and Docker Compose
- AWS credentials for Bedrock (or set `APP_MODE=mock` for frontend-only dev)

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd arbiter-ai
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Edit .env files with your values (see App Modes below)

# 2. Start infrastructure (Postgres + Redis)
make up

# 3. Install dependencies
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..

# 4. Run database migrations
make migrate

# 4b. Seed Armory catalog entries (recommended for local dev)
cd backend && uv run python -m scripts.seed_catalog && cd ..

# 4c. (Optional) Run live sync jobs manually
cd backend && uv run python -m scripts.sync_catalog_live && cd ..
cd backend && uv run python -m scripts.sync_open_rules && cd ..

# 5. Start dev servers (in separate terminals)
make backend    # → http://localhost:8000
make frontend   # → http://localhost:3000
```

If the frontend shows offline fallback data after a restart, confirm backend health first:

```bash
curl http://localhost:8000/health
```

Or use Docker Compose for everything:

```bash
docker compose up --build
```

## Make Targets

| Command         | Description                          |
| --------------- | ------------------------------------ |
| `make up`       | Start Postgres + Redis containers    |
| `make down`     | Stop Docker services                 |
| `make migrate`  | Run Alembic DB migrations            |
| `make backend`  | Start FastAPI dev server (port 8000) |
| `make frontend` | Start Next.js dev server (port 3000) |
| `make worker`   | Start Celery worker process           |
| `make beat`     | Start Celery Beat scheduler           |
| `make sync-catalog` | One-shot BGG metadata sync        |
| `make sync-open-rules` | One-shot Open5e rules sync     |
| `make preflight-sandbox` | Run sandbox readiness checks   |
| `make preflight-production` | Run production readiness checks |
| `make test`     | Run backend + frontend test suites   |
| `make test-backend` | Run backend pytest suite         |
| `make test-frontend` | Run frontend Vitest suite       |
| `make lint`     | Run backend + frontend linters       |
| `make lint-backend` | Run ruff + targeted mypy checks  |
| `make lint-frontend` | Run frontend eslint            |
| `make dev`      | Start Docker + print instructions    |

## App Modes

The `APP_MODE` env var controls the entire runtime tier. Set it in `backend/.env`:

| Mode         | DB  | Auth | LLM/Embeddings | Stripe    | Use Case                          |
| ------------ | --- | ---- | -------------- | --------- | --------------------------------- |
| `mock`       | ❌  | ❌   | ❌ (faked)     | ❌        | Frontend-only dev, no keys needed |
| `sandbox`    | ✅  | ✅   | ✅ (Bedrock)   | Test keys | Full local dev (default)          |
| `production` | ✅  | ✅   | ✅ (Bedrock)   | Live keys | AWS deployment                    |

**Frontend-only dev** — just want to work on the UI?

```bash
# backend/.env
APP_MODE=mock
```

No database, no Redis, no API keys. All data is faked.

**Full local dev** — testing the real pipeline?

```bash
# backend/.env
APP_MODE=sandbox
DATABASE_URL=postgresql+asyncpg://arbiter:arbiter_dev@localhost:5432/arbiter
NEXTAUTH_SECRET=changeme_in_production_secret_key_12345
# AWS credentials for Bedrock (set via env, profile, or IAM role)
```

**Production** — see [docs/aws-deployment.md](docs/aws-deployment.md).

## Environment Variables

See these templates:

- `backend/.env.example` (local development baseline)
- `backend/.env.sandbox.example` (AWS sandbox/staging)
- `backend/.env.production.example` (AWS production)
- `frontend/.env.example` (local development baseline)
- `frontend/.env.sandbox.example` (AWS sandbox/staging)
- `frontend/.env.production.example` (AWS production)

### Backend (`backend/.env`)

| Variable                | Mode     | Description                                     |
| ----------------------- | -------- | ----------------------------------------------- |
| `APP_MODE`              | All      | `mock`, `sandbox`, or `production`              |
| `DATABASE_URL`          | sandbox+ | PostgreSQL connection string                    |
| `REDIS_URL`             | sandbox+ | Redis for Celery + rate limiting                |
| `NEXTAUTH_SECRET`       | sandbox+ | Must match frontend `AUTH_SECRET`               |
| `STRIPE_SECRET_KEY`     | sandbox+ | Stripe API key (test or live)                   |
| `STRIPE_WEBHOOK_SECRET` | sandbox+ | Stripe webhook signature                        |
| `AWS_REGION`            | sandbox+ | AWS region for Bedrock (default: `us-east-1`)   |
| `ALLOWED_ORIGINS`       | All      | CORS origins (comma-separated)                   |
| `APP_BASE_URL`          | All      | Canonical frontend URL for Stripe/invite links   |
| `TRUSTED_PROXY_HOPS`    | All      | Trusted proxy depth for `X-Forwarded-For`        |
| `CATALOG_SYNC_ENABLED`  | sandbox+ | Enable periodic metadata sync task               |
| `CATALOG_SYNC_CRON`     | sandbox+ | Cron for metadata sync (`m h dom mon dow`)       |
| `CATALOG_RANKED_GAME_LIMIT` | sandbox+ | Max BGG ranked entries per sync             |
| `OPEN_RULES_SYNC_ENABLED` | sandbox+ | Enable periodic open-license rules ingestion   |
| `OPEN_RULES_SYNC_CRON`  | sandbox+ | Cron for open-rules sync (`m h dom mon dow`)     |
| `OPEN_RULES_MAX_DOCUMENTS` | sandbox+ | Max Open5e documents per run                 |
| `OPEN_RULES_ALLOWED_LICENSES` | sandbox+ | Comma keywords (e.g., CC/OGL/ORC)      |
| `OPEN_RULES_FORCE_REINDEX` | sandbox+ | Force rebuild vectors even if unchanged       |

When deploying to ECS with Secrets Manager JSON-key injection, only map keys your runtime actually uses. For Bedrock + pgvector, do not include `PINECONE_API_KEY` in task-definition `secrets`.
For split backend/frontend DB drivers in AWS, keep both keys in the secret payload:
- `DATABASE_URL` (backend, asyncpg)
- `FRONTEND_DATABASE_URL` (frontend, postgres sync driver)

### Frontend (`frontend/.env`)

| Variable          | Required | Description                          |
| ----------------- | -------- | ------------------------------------ |
| `APP_MODE`        | Recommended | `sandbox` or `production` (email fallback behavior) |
| `AUTH_SECRET`     | ✅       | JWT signing key (must match backend) |
| `AUTH_TRUST_HOST` | Dev only | Set to `true` for localhost          |
| `NEXTAUTH_URL`    | Dev only | `http://localhost:3000`              |
| `NEXT_PUBLIC_API_URL` | Optional | Backend API base (defaults to same-origin `/api/v1`) |
| `BACKEND_ORIGIN` | Dev optional | Next.js local proxy target (default `http://localhost:8000`) |
| `DATABASE_URL`    | ✅       | PostgreSQL for NextAuth adapter      |
| `EMAIL_PROVIDER`  | Recommended | `ses` (default), `brevo`, or `console` |
| `EMAIL_SERVER`    | Required for SES in production | SMTP URI (recommended for SES via Secrets Manager) |
| `SES_SMTP_*`      | Optional alt to `EMAIL_SERVER` | Host/port/user/pass config for SES SMTP |
| `BREVO_API_KEY`   | Only when `EMAIL_PROVIDER=brevo` | Brevo API key |
| `SANDBOX_EMAIL_BYPASS_ENABLED` | Sandbox optional | `true` enables allowlisted credentials bypass |
| `EMAIL_FROM`      | Optional | Sender address (default `noreply@getquuie.com`) |
| `EMAIL_FROM_NAME` | Optional | Sender display name (default `Arbiter AI`) |

Local dev default: leave `NEXT_PUBLIC_API_URL` unset and Next.js will call `/api/v1` same-origin, then proxy to `BACKEND_ORIGIN` (`http://localhost:8000` by default).

## API Documentation

With the backend running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

The API exposes user, catalog, adjudication, billing, and admin route modules. See [spec.md](spec.md) for the full routes table.

## Armory Statuses

- `READY` / `INDEXED` / `COMPLETE` / `PUBLISHED`: official rules are indexed and can be queried without user upload.
- `UPLOAD_REQUIRED`: metadata/discovery entry only; user must upload a rulebook for adjudication.

`scripts.seed_catalog.py` seeds metadata entries plus live sources (BGG Hot + Ranked + Open5e open-license docs).  
For ongoing production refresh, run Celery Beat with `CATALOG_SYNC_ENABLED=true` and `OPEN_RULES_SYNC_ENABLED=true`.

## Testing

```bash
# Full quality gate (backend + frontend)
make test

# Backend only
make test-backend

# Frontend only
make test-frontend

# Full lint gate (backend + frontend)
make lint
```

## Deployment Preflight

Run preflight before promoting a build to sandbox or production:

```bash
# Validates env + DB + Redis + provider stack + embedding probe
make preflight-sandbox

# Validates env + DB + Redis + provider stack + embedding + LLM probes
make preflight-production
```

For CI parsing, run JSON mode directly:

```bash
cd backend && uv run python -m scripts.preflight --expected-mode production --probe-embedding --probe-llm --json
```

`--probe-embedding` and `--probe-llm` call live Bedrock APIs and incur normal provider usage costs.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app factory
│   │   ├── config.py         # Pydantic Settings (all env vars)
│   │   ├── api/
│   │   │   ├── deps.py       # Auth (NextAuth JWT), DB, Redis injection
│   │   │   ├── middleware.py  # RequestID, logging, error handling
│   │   │   └── routes/       # Route modules (API + mock parity)
│   │   ├── models/
│   │   │   ├── tables.py     # SQLAlchemy ORM (10 tables)
│   │   │   ├── schemas.py    # Pydantic request/response schemas
│   │   │   └── database.py   # Async engine + session factory
│   │   └── core/             # Ingestion, retrieval, judge engine
│   ├── alembic/              # DB migrations
│   └── tests/                # pytest suite
├── frontend/
│   └── src/
│       ├── app/              # Next.js App Router (14 routes)
│       ├── lib/api.ts        # Typed API client (30 methods)
│       ├── lib/api.test.ts   # Frontend API client regression tests
│       └── components/       # Shadcn UI components
├── docs/
│   └── aws-deployment.md     # AWS deployment guide
├── docker-compose.yml        # Full-stack Docker setup
├── Makefile                  # Dev command shortcuts
├── .env.example              # Environment variable template
├── prd.md                    # Product requirements
├── spec.md                   # Technical specification
└── plan.md                   # Implementation checklist
```

## Deployment

See [docs/aws-deployment.md](docs/aws-deployment.md) for the AWS deployment guide covering ECS Fargate, RDS, ElastiCache, and CI/CD.
GitHub Actions deploy gate is versioned at `.github/workflows/deploy.yml` and requires preflight success before ECS rollout.
For ECS, runtime config comes from task-definition environment/secrets injection, not local `.env` files.
Terraform provisions four ECS services (`backend`, `frontend`, `worker`, `beat`) plus a shared EFS upload mount so async ingestion works across backend/worker tasks.
Deploy workflow supports sandbox/prod targeting via `deploy_mode`/`tf_state_key` inputs (or repo vars `DEPLOY_MODE`/`TF_STATE_KEY`).

ECS backend task-definition baseline is versioned in-repo at `infra/ecs/backend-task-definition.json` (Bedrock + pgvector, no Pinecone secret mapping).

## License

Proprietary — All rights reserved.
