# AWS Deployment Guide — Arbiter AI

This guide covers deploying Arbiter AI to AWS using ECS Fargate, RDS, and ElastiCache.

## Architecture Overview

```mermaid
graph TD
    subgraph "AWS Cloud"
        CF[CloudFront CDN] --> ALB[Application Load Balancer]
        ALB --> ECS_FE[ECS: Frontend<br/>Next.js]
        ALB --> ECS_BE[ECS: Backend<br/>FastAPI]
        ECS_BE --> RDS[(RDS PostgreSQL 16)]
        ECS_BE --> EC[(ElastiCache Redis)]
        ECS_BE --> SM[Secrets Manager]
        ECS_BE --> BR[AWS Bedrock]
        ECS_BE --> STR[Stripe API]
        R53[Route 53] --> CF
    end
    Users --> R53
```

## Prerequisites

- AWS CLI configured with appropriate IAM permissions
- Docker installed locally
- A registered domain (e.g., `arbiter-ai.com`)
- Stripe account with API keys
- AWS account with Bedrock model access (Claude + Titan embed)

---

## App Modes & Environment Configuration

Arbiter AI uses two env vars to control runtime behavior:

| Env Var    | Values                                 | Controls                                                  |
| ---------- | -------------------------------------- | --------------------------------------------------------- |
| `APP_MODE` | `mock`, `sandbox`, `production`        | **What features run** — providers, billing, auth bypass   |
| `APP_ENV`  | `development`, `staging`, `production` | **How strict the app is** — error detail, security guards |

### Mode Comparison

| Capability       | `mock`      | `sandbox`        | `production`         |
| ---------------- | ----------- | ---------------- | -------------------- |
| Database         | ❌ Bypassed | ✅ Real Postgres | ✅ Real Postgres     |
| Auth (JWT)       | ❌ Bypassed | ✅ Full auth     | ✅ Full auth         |
| LLM / Embeddings | ❌ Faked    | ✅ AWS Bedrock   | ✅ AWS Bedrock       |
| Stripe Billing   | ❌ Faked    | ✅ Test keys     | ✅ Live keys         |
| Rate Limiting    | ❌ Off      | ✅ Redis-backed  | ✅ Redis-backed      |
| Security Guards  | Relaxed     | Warn on missing  | **Crash on missing** |
| Error Messages   | Detailed    | Detailed         | Sanitized            |

### Switching Modes

**Local development** (default):

```bash
APP_MODE=sandbox
APP_ENV=development
```

**Frontend-only dev** (no backend deps):

```bash
APP_MODE=mock
APP_ENV=development
```

**Staging / QA**:

```bash
APP_MODE=sandbox
APP_ENV=staging
```

**Production deployment**:

```bash
APP_MODE=production
APP_ENV=production
```

> [!CAUTION]
> In `production` mode, the app **will not start** if `NEXTAUTH_SECRET`, `STRIPE_SECRET_KEY`, or AWS credentials are missing. This is intentional — it prevents silently running without auth or billing.

### Environment Templates

Use environment-specific templates as your starting point:

```bash
# Backend
cp backend/.env.sandbox.example backend/.env      # sandbox/staging
cp backend/.env.production.example backend/.env   # production

# Frontend
cp frontend/.env.sandbox.example frontend/.env      # sandbox/staging
cp frontend/.env.production.example frontend/.env   # production
```

Then replace placeholder values and store them in AWS Secrets Manager/SSM.

### Frontend Environment

The frontend needs these env vars in all modes:

```bash
# frontend/.env
AUTH_SECRET=<must-match-backend-NEXTAUTH_SECRET>
AUTH_TRUST_HOST=true          # Required for non-production hosts
NEXTAUTH_URL=http://localhost:3000   # Or your production URL
NEXT_PUBLIC_API_URL=/api/v1          # Recommended when ALB routes /api/* to backend
DATABASE_URL=postgresql://arbiter:arbiter_dev@localhost:5432/arbiter
```

> [!IMPORTANT]
> `AUTH_SECRET` (frontend) and `NEXTAUTH_SECRET` (backend) **must be the same value**. They are the JWT signing key shared between NextAuth and the FastAPI JWT validator.
> `NEXT_PUBLIC_API_URL` is a build-time variable for Next.js client bundles. Ensure it is injected during Docker build (not only at runtime).

## Step 1: Create Infrastructure

### 1a. ECR Repositories

```bash
# Create repos for both containers
aws ecr create-repository --repository-name arbiter-ai/backend
aws ecr create-repository --repository-name arbiter-ai/frontend
```

### 1b. RDS PostgreSQL

```bash
aws rds create-db-instance \
  --db-instance-identifier arbiter-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username arbiter \
  --master-user-password <STRONG_PASSWORD> \
  --allocated-storage 20 \
  --vpc-security-group-ids <SG_ID> \
  --db-name arbiter \
  --backup-retention-period 7 \
  --multi-az false \
  --storage-encrypted
```

> [!IMPORTANT]
> Ensure your Postgres target supports the `vector` extension (`CREATE EXTENSION vector;`) before running Alembic migrations.

### 1c. ElastiCache Redis

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id arbiter-redis \
  --cache-node-type cache.t4g.micro \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1
```

### 1d. Secrets Manager

Store all env vars from `.env.example` in Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name arbiter-ai/production \
  --secret-string '{
    "DATABASE_URL": "postgresql+asyncpg://arbiter:<PW>@<RDS_ENDPOINT>:5432/arbiter",
    "FRONTEND_DATABASE_URL": "postgresql://arbiter:<PW>@<RDS_ENDPOINT>:5432/arbiter",
    "REDIS_URL": "redis://<ELASTICACHE_ENDPOINT>:6379/0",
    "APP_MODE": "production",
    "LLM_PROVIDER": "bedrock",
    "EMBEDDING_PROVIDER": "bedrock",
    "VECTOR_STORE_PROVIDER": "pgvector",
    "AWS_REGION": "us-east-1",
    "NEXTAUTH_SECRET": "<RANDOM_32_CHARS>",
    "STRIPE_SECRET_KEY": "sk_live_...",
    "STRIPE_WEBHOOK_SECRET": "whsec_...",
    "STRIPE_PRICE_ID": "price_...",
    "ALLOWED_ORIGINS": "https://arbiter-ai.com",
    "APP_BASE_URL": "https://arbiter-ai.com",
    "TRUSTED_PROXY_HOPS": "1",
    "APP_ENV": "production",
    "LOG_LEVEL": "INFO",
    "CATALOG_SYNC_ENABLED": "true",
    "CATALOG_SYNC_CRON": "15 */6 * * *",
    "CATALOG_RANKED_GAME_LIMIT": "1000",
    "OPEN_RULES_SYNC_ENABLED": "true",
    "OPEN_RULES_SYNC_CRON": "45 4 * * *",
    "OPEN_RULES_MAX_DOCUMENTS": "20",
    "OPEN_RULES_ALLOWED_LICENSES": "creative commons,open gaming license,orc",
    "OPEN_RULES_FORCE_REINDEX": "false",
    "EMAIL_SERVER": "smtp://SMTP_USERNAME:SMTP_PASSWORD@email-smtp.us-east-1.amazonaws.com:587"
  }'
```

> [!IMPORTANT]
> ECS fails startup if your task definition references a JSON key that does not exist in the secret payload.  
> If you are using `pgvector` + Bedrock, do **not** reference `PINECONE_API_KEY` (or other unused keys) in `containerDefinitions[].secrets`.

---

## Step 2: Build and Push Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build and push backend
docker build -t arbiter-ai/backend ./backend
docker tag arbiter-ai/backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/arbiter-ai/backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/arbiter-ai/backend:latest

# Build and push frontend
docker build --build-arg NEXT_PUBLIC_API_URL=/api/v1 -t arbiter-ai/frontend ./frontend
docker tag arbiter-ai/frontend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/arbiter-ai/frontend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/arbiter-ai/frontend:latest
```

---

## Step 3: ECS Fargate Setup

### 3a. Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name arbiter-ai --capacity-providers FARGATE
```

Use the repo template as the baseline task definition:

- `infra/ecs/backend-task-definition.json`

### 3b. Task Definitions

Create task definitions for both services. Key configuration:

| Service  | CPU | Memory  | Port | Health Check  |
| -------- | --- | ------- | ---- | ------------- |
| Backend  | 512 | 1024 MB | 8000 | `GET /health` |
| Frontend | 256 | 512 MB  | 3000 | `GET /`       |

> [!IMPORTANT]
> The task execution role must have permissions to pull from ECR and read from Secrets Manager. The task role must also have Bedrock invoke permissions.

Register the backend task definition from the template:

```bash
aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/backend-task-definition.json
```

### 3c. Environment Variables

In the ECS task definition, reference Secrets Manager:

```json
{
  "secrets": [
    {
      "name": "DATABASE_URL",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCT>:secret:arbiter-ai/production:DATABASE_URL::"
    }
  ]
}
```

Backend (Bedrock + pgvector) should only map keys you actually use, for example:

```json
{
  "secrets": [
    { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:...:secret:arbiter-ai/production:DATABASE_URL::" },
    { "name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:...:secret:arbiter-ai/production:REDIS_URL::" },
    { "name": "NEXTAUTH_SECRET", "valueFrom": "arn:aws:secretsmanager:...:secret:arbiter-ai/production:NEXTAUTH_SECRET::" },
    { "name": "STRIPE_SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:...:secret:arbiter-ai/production:STRIPE_SECRET_KEY::" },
    { "name": "STRIPE_WEBHOOK_SECRET", "valueFrom": "arn:aws:secretsmanager:...:secret:arbiter-ai/production:STRIPE_WEBHOOK_SECRET::" }
  ],
  "environment": [
    { "name": "APP_MODE", "value": "production" },
    { "name": "APP_ENV", "value": "production" },
    { "name": "AWS_REGION", "value": "us-east-1" },
    { "name": "LLM_PROVIDER", "value": "bedrock" },
    { "name": "EMBEDDING_PROVIDER", "value": "bedrock" },
    { "name": "VECTOR_STORE_PROVIDER", "value": "pgvector" },
    { "name": "RERANKER_PROVIDER", "value": "flashrank" },
    { "name": "CATALOG_SYNC_ENABLED", "value": "true" },
    { "name": "CATALOG_SYNC_CRON", "value": "15 */6 * * *" },
    { "name": "CATALOG_RANKED_GAME_LIMIT", "value": "1000" },
    { "name": "OPEN_RULES_SYNC_ENABLED", "value": "true" },
    { "name": "OPEN_RULES_SYNC_CRON", "value": "45 4 * * *" },
    { "name": "OPEN_RULES_MAX_DOCUMENTS", "value": "20" },
    { "name": "OPEN_RULES_ALLOWED_LICENSES", "value": "creative commons,open gaming license,orc" }
  ]
}
```

### 3d. Run Worker + Beat Services

Use separate ECS services for:

- `backend-api` (FastAPI)
- `backend-worker` (`celery -A app.workers.celery_app worker --loglevel=info`)
- `backend-beat` (`celery -A app.workers.celery_app beat --loglevel=info`)

`backend-worker` processes PDF ingestion and open-license rules embedding.  
`backend-beat` schedules periodic catalog and open-rules sync tasks.

---

## Step 4: ALB + Route 53 + ACM

1. **ACM Certificate**: Request a certificate for `arbiter-ai.com` and `*.arbiter-ai.com`
2. **ALB**: Create an Application Load Balancer with HTTPS listener
3. **Target Groups**:
   - `/api/*` → Backend service (port 8000)
   - `/*` → Frontend service (port 3000)
4. **Route 53**: Create A record aliased to the ALB

---

## Step 5: Database Migration

Run Alembic migrations from a one-off ECS task:

```bash
aws ecs run-task \
  --cluster arbiter-ai \
  --task-definition arbiter-backend \
  --overrides '{"containerOverrides": [{"name": "backend", "command": ["alembic", "upgrade", "head"]}]}'
```

---

## Step 5b: Deployment Preflight Gate

Before promoting sandbox or production, run the backend preflight checks:

```bash
# Sandbox / staging gate
make preflight-sandbox

# Production gate
make preflight-production
```

This validates:

- Environment mode + required keys (`APP_MODE`, auth/billing/provider requirements)
- Database connectivity (`SELECT 1`)
- Redis connectivity (`PING`)
- Provider stack instantiation (LLM/embedder/vector/reranker/parser)
- Optional live Bedrock probes (embedding for sandbox, embedding + LLM for production)

For CI pipelines, use JSON output:

```bash
cd backend && uv run python -m scripts.preflight --expected-mode production --probe-embedding --probe-llm --json
```

> [!NOTE]
> The probe flags make live Bedrock calls and incur normal API usage cost. Keep them enabled for release gates, not every local edit loop.

---

## Step 6: Stripe Webhook

Configure Stripe to send webhook events to your production URL:

1. Go to [Stripe Dashboard → Developers → Webhooks](https://dashboard.stripe.com/webhooks)
2. Add endpoint: `https://arbiter-ai.com/api/v1/billing/webhooks/stripe`
3. Select events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
4. Copy the signing secret → update `STRIPE_WEBHOOK_SECRET` in Secrets Manager

---

## Estimated Monthly Cost (Starter)

| Service               | Spec                    | Est. Cost      |
| --------------------- | ----------------------- | -------------- |
| ECS Fargate (3 tasks) | API + Worker + Beat     | ~$33           |
| RDS PostgreSQL        | db.t4g.micro, 20 GB     | ~$15           |
| ElastiCache Redis     | cache.t4g.micro         | ~$12           |
| ALB                   | Standard                | ~$16           |
| CloudFront            | ~10 GB transfer         | ~$1            |
| Secrets Manager       | 10 secrets              | ~$4            |
| ECR                   | ~2 GB storage           | ~$1            |
| **Total**             |                         | **~$74/month** |

> [!TIP]
> Use AWS Free Tier where eligible. RDS and ElastiCache micro instances are free-tier eligible for 12 months.

---

## CI/CD with GitHub Actions

Use the repo workflow at `.github/workflows/deploy.yml`. It enforces a required `preflight` job before `deploy`.

Workflow behavior:

- `workflow_dispatch` input chooses `sandbox` or `production`
- Runs an ECS one-off task that executes `python -m scripts.preflight ...`
- Blocks deploy when preflight exit code is non-zero
- Deploys by updating the target ECS service only after preflight succeeds

Configure these repository values:

- `AWS_REGION`
- `ECS_CLUSTER`
- `ECS_SUBNETS` (comma-separated subnet IDs)
- `ECS_SECURITY_GROUPS` (comma-separated SG IDs)
- `ECS_BACKEND_TASKDEF_SANDBOX`
- `ECS_BACKEND_TASKDEF_PRODUCTION`
- `ECS_BACKEND_SERVICE_SANDBOX`
- `ECS_BACKEND_SERVICE_PRODUCTION`
- `ECS_BACKEND_CONTAINER_NAME` (optional; defaults to `backend`)
- `ECS_ASSIGN_PUBLIC_IP` (optional; `ENABLED`/`DISABLED`)

Configure this repository secret:

- `AWS_DEPLOY_ROLE_ARN` (OIDC assumable role with ECS + IAM permissions)

Run it from Actions UI:

```text
Actions → Deploy ECS → Run workflow
```

---

## Checklist Before Go-Live

- [ ] RDS instance created with strong password
- [ ] ElastiCache cluster running
- [ ] All secrets stored in Secrets Manager
- [ ] ECR images built and pushed
- [ ] ECS services running and healthy
- [ ] Worker + Beat services running and healthy
- [ ] ALB routing `/api/*` → backend, `/*` → frontend
- [ ] ACM certificate issued and attached to ALB
- [ ] Route 53 A record pointing to ALB
- [ ] Alembic migrations run against production DB
- [ ] Stripe webhook configured with production URL
- [ ] `APP_ENV=production` set in Secrets Manager
- [ ] `ALLOWED_ORIGINS` set to production domain
- [ ] `CATALOG_SYNC_ENABLED=true` and `OPEN_RULES_SYNC_ENABLED=true` for automatic refresh
- [ ] `make preflight-production` passes for the exact release image/env
- [ ] Smoke test: hit `/health`, `/api/v1/catalog/`, sign in, run a query
