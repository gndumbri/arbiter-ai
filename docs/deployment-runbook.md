# Arbiter AI — Deployment Runbook

## Overview

This runbook covers everything needed to go from local dev to a running sandbox/production environment on AWS using **Terraform + Secrets Manager + ECS Fargate**.

---

## Step 1: Decide Your Environments

| Environment | `APP_MODE`   | Purpose                          |
| ----------- | ------------ | -------------------------------- |
| Local dev   | `mock`       | No keys, no DB, pure UI work     |
| Local full  | `sandbox`    | Real local DB/Redis, test keys   |
| AWS Sandbox | `sandbox`    | Real AWS infra, test Stripe keys |
| AWS Prod    | `production` | Live everything                  |

> [!IMPORTANT]
> The app **self-validates** on startup based on `APP_MODE`. In `production`, it will **refuse to start** if required keys are missing.

---

## Step 2: Create Secrets in AWS Secrets Manager

### What you need from your platform team

Ask them to create **one secret per environment** using the naming convention:

```
arbiter-ai/sandbox    ← for sandbox
arbiter-ai/production ← for production
```

Each secret should be a **JSON object** with these keys:

```json
{
  "DATABASE_URL": "postgresql+asyncpg://user:pass@rds-host:5432/arbiter",
  "REDIS_URL": "redis://elasticache-host:6379/0",
  "NEXTAUTH_SECRET": "<generate with: openssl rand -base64 32>",
  "STRIPE_SECRET_KEY": "sk_test_... (sandbox) or sk_live_... (prod)",
  "STRIPE_WEBHOOK_SECRET": "whsec_...",
  "STRIPE_PRICE_ID": "price_...",
  "BREVO_API_KEY": "xkeysib-... (for magic-link sign-in emails)"
}
```

### How to generate them

```bash
# AUTH_SECRET — must be the SAME value in backend and frontend
openssl rand -base64 32
```

> [!CAUTION]
> `NEXTAUTH_SECRET` MUST match between the backend ECS task and the frontend deployment (Vercel/Amplify). If they differ, JWT verification will fail silently and all authenticated API calls will return 401.

### CLI shortcut (if you create them yourself)

```bash
aws secretsmanager create-secret \
  --name "arbiter-ai/sandbox" \
  --secret-string '{
    "DATABASE_URL": "postgresql+asyncpg://arbiter:PASSWORD@your-rds.us-east-1.rds.amazonaws.com:5432/arbiter",
    "REDIS_URL": "redis://your-elasticache.us-east-1.cache.amazonaws.com:6379/0",
    "NEXTAUTH_SECRET": "<paste generated value>",
    "STRIPE_SECRET_KEY": "sk_test_...",
    "STRIPE_WEBHOOK_SECRET": "whsec_...",
    "STRIPE_PRICE_ID": "price_...",
    "BREVO_API_KEY": "xkeysib-..."
  }' \
  --region us-east-1
```

---

## Step 3: IAM Roles (Ask Platform Team)

You need **two IAM roles**. Tell your platform team:

### 3a. ECS Execution Role (`arbiter-ecs-execution-role`)

> "I need an ECS execution role that can pull secrets from Secrets Manager and pull images from ECR."

Required policies:

- `AmazonECSTaskExecutionRolePolicy` (managed)
- Inline policy for Secrets Manager:

```json
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": [
    "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:arbiter-ai/*"
  ]
}
```

### 3b. Task Role (`arbiter-backend-task-role`)

> "I need a task role that lets the running container call Bedrock for LLM/embeddings."

Required policies:

```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
  "Resource": [
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-*",
    "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
  ]
}
```

> [!NOTE]
> With the Task Role granting Bedrock access, you do **NOT** need AWS access keys in Secrets Manager. The `boto3` SDK automatically uses the task role credentials via the ECS metadata endpoint.

---

## Step 4: Terraform Configuration

### 4a. Variable file per environment

```hcl
# environments/sandbox.tfvars
environment     = "sandbox"
app_mode        = "sandbox"
app_base_url    = "https://sandbox.arbiter-ai.com"
allowed_origins = "https://sandbox.arbiter-ai.com"
secret_name     = "arbiter-ai/sandbox"
```

```hcl
# environments/production.tfvars
environment     = "production"
app_mode        = "production"
app_base_url    = "https://arbiter-ai.com"
allowed_origins = "https://arbiter-ai.com,https://www.arbiter-ai.com"
secret_name     = "arbiter-ai/production"
```

### 4b. ECS task definition in Terraform

Reference the existing template at `infra/ecs/backend-task-definition.json` or use Terraform resources directly:

```hcl
resource "aws_ecs_task_definition" "backend" {
  family                   = "arbiter-backend-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.backend_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${var.ecr_repo_url}:${var.image_tag}"
    essential = true

    portMappings = [{ containerPort = 8000 }]

    # ─── Non-sensitive config (changes per environment via .tfvars) ────
    environment = [
      { name = "APP_MODE",             value = var.app_mode },
      { name = "APP_ENV",              value = var.environment },
      { name = "LOG_LEVEL",            value = var.environment == "production" ? "INFO" : "DEBUG" },
      { name = "ALLOWED_ORIGINS",      value = var.allowed_origins },
      { name = "APP_BASE_URL",         value = var.app_base_url },
      { name = "TRUSTED_PROXY_HOPS",   value = "1" },
      { name = "LLM_PROVIDER",         value = "bedrock" },
      { name = "EMBEDDING_PROVIDER",   value = "bedrock" },
      { name = "VECTOR_STORE_PROVIDER", value = "pgvector" },
      { name = "RERANKER_PROVIDER",    value = "flashrank" },
    ]

    # ─── Sensitive values (pulled from Secrets Manager at startup) ─────
    secrets = [
      { name = "DATABASE_URL",          valueFrom = "${var.secret_arn}:DATABASE_URL::" },
      { name = "REDIS_URL",             valueFrom = "${var.secret_arn}:REDIS_URL::" },
      { name = "NEXTAUTH_SECRET",       valueFrom = "${var.secret_arn}:NEXTAUTH_SECRET::" },
      { name = "STRIPE_SECRET_KEY",     valueFrom = "${var.secret_arn}:STRIPE_SECRET_KEY::" },
      { name = "STRIPE_WEBHOOK_SECRET", valueFrom = "${var.secret_arn}:STRIPE_WEBHOOK_SECRET::" },
      { name = "STRIPE_PRICE_ID",       valueFrom = "${var.secret_arn}:STRIPE_PRICE_ID::" },
    ]

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 20
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/arbiter-backend-${var.environment}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}
```

### 4c. Deploy

```bash
# Sandbox
terraform plan  -var-file=environments/sandbox.tfvars
terraform apply -var-file=environments/sandbox.tfvars

# Production
terraform plan  -var-file=environments/production.tfvars
terraform apply -var-file=environments/production.tfvars
```

---

## Step 5: Frontend Deployment (Vercel / Amplify)

The frontend needs these env vars set in the hosting platform dashboard:

| Variable          | Sandbox                           | Production                        |
| ----------------- | --------------------------------- | --------------------------------- |
| `AUTH_SECRET`     | Same as backend `NEXTAUTH_SECRET` | Same as backend `NEXTAUTH_SECRET` |
| `AUTH_TRUST_HOST` | `true`                            | `true`                            |
| `NEXTAUTH_URL`    | `https://sandbox.arbiter-ai.com`  | `https://arbiter-ai.com`          |
| `DATABASE_URL`    | RDS connection string (non-async) | RDS connection string (non-async) |
| `BREVO_API_KEY`   | Your Brevo key                    | Your Brevo key                    |
| `EMAIL_FROM`      | `noreply@arbiter-ai.com`          | `noreply@arbiter-ai.com`          |

> [!WARNING]
> The frontend `DATABASE_URL` uses the **synchronous** driver (`postgresql://`), NOT the async one (`postgresql+asyncpg://`) that the backend uses. Same RDS instance, different connection string format.

---

## Step 6: Pre-Flight Checklist

Before you go live, verify:

- [ ] **Secrets Manager** has all 7 keys populated for the target environment
- [ ] **ECS execution role** can read from `arbiter-ai/*` in Secrets Manager
- [ ] **ECS task role** has Bedrock `InvokeModel` permission
- [ ] **RDS** is accessible from the ECS security group (port 5432)
- [ ] **ElastiCache/Redis** is accessible from the ECS security group (port 6379)
- [ ] **pgvector extension** is enabled on the RDS instance (`CREATE EXTENSION IF NOT EXISTS vector;`)
- [ ] **DB migrations** have been run (tables exist: `users`, `accounts`, `verification_tokens`, etc.)
- [ ] **`NEXTAUTH_SECRET`** matches between backend secret and frontend env
- [ ] **Stripe webhook** is pointed at `https://<domain>/api/v1/billing/webhooks/stripe`
- [ ] **Brevo sender domain** is verified (or using a verified sender email)
- [ ] **Health check** passes: `curl https://<domain>/health`

---

## Quick Reference: What Goes Where

```
┌─────────────────────────────────────────────────────────┐
│ Secrets Manager (arbiter-ai/{env})                      │
│  DATABASE_URL, REDIS_URL, NEXTAUTH_SECRET,              │
│  STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,              │
│  STRIPE_PRICE_ID, BREVO_API_KEY                         │
└─────────────────────────────┬───────────────────────────┘
                              │ pulled at container start
┌─────────────────────────────▼───────────────────────────┐
│ ECS Task Definition (environment block)                 │
│  APP_MODE, APP_ENV, ALLOWED_ORIGINS, APP_BASE_URL,      │
│  LLM_PROVIDER, EMBEDDING_PROVIDER, RERANKER_PROVIDER,   │
│  VECTOR_STORE_PROVIDER, LOG_LEVEL, TRUSTED_PROXY_HOPS   │
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│ IAM Task Role (attached to running container)           │
│  bedrock:InvokeModel → no AWS keys needed in env        │
└─────────────────────────────────────────────────────────┘
```

---

## What To Copy-Paste to Your Platform Team

> We need:
>
> 1. **A Secrets Manager secret** called `arbiter-ai/sandbox` (and later `arbiter-ai/production`) — I'll give you the JSON values to populate
> 2. **An ECS execution role** with `AmazonECSTaskExecutionRolePolicy` + read access to `arbiter-ai/*` secrets
> 3. **An ECS task role** with `bedrock:InvokeModel` on Claude 3.5 Sonnet and Titan Embed v2 models
> 4. **An RDS Postgres 16 instance** with the `vector` extension enabled
> 5. **An ElastiCache Redis 7 cluster** (single node is fine for sandbox)
> 6. **Security groups** allowing ECS → RDS (5432) and ECS → Redis (6379)
> 7. **An ECR repository** called `arbiter-ai/backend` for the Docker images
> 8. **A CloudWatch log group** at `/ecs/arbiter-backend-sandbox`
