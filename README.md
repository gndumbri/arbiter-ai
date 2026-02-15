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
| Queue         | Redis 7 + Celery                    | Async PDF ingestion pipeline         |
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

# 5. Start dev servers (in separate terminals)
make backend    # → http://localhost:8000
make frontend   # → http://localhost:3000
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
| `make test`     | Run backend pytest suite             |
| `make lint`     | Run ruff + mypy                      |
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

When deploying to ECS with Secrets Manager JSON-key injection, only map keys your runtime actually uses. For Bedrock + pgvector, do not include `PINECONE_API_KEY` in task-definition `secrets`.

### Frontend (`frontend/.env`)

| Variable          | Required | Description                          |
| ----------------- | -------- | ------------------------------------ |
| `AUTH_SECRET`     | ✅       | JWT signing key (must match backend) |
| `AUTH_TRUST_HOST` | Dev only | Set to `true` for localhost          |
| `NEXTAUTH_URL`    | Dev only | `http://localhost:3000`              |
| `DATABASE_URL`    | ✅       | PostgreSQL for NextAuth adapter      |

## API Documentation

With the backend running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

The API has 43 endpoints across 12 route modules. See [spec.md](spec.md) for the full routes table.

## Testing

```bash
# Backend (73 tests)
make test

# Linting
make lint
```

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
│   └── tests/                # pytest suite (73 tests)
├── frontend/
│   └── src/
│       ├── app/              # Next.js App Router (14 routes)
│       ├── lib/api.ts        # Typed API client (30 methods)
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

## License

Proprietary — All rights reserved.
