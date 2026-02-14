---
description: how to start the development environment
---

// turbo-all

## Steps

1. Start Docker services:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai && docker compose up -d
```

2. Install backend dependencies:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv sync
```

3. Run database migrations:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run alembic upgrade head
```

4. Start Celery worker (background):

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run celery -A app.workers.tasks worker --loglevel=info
```

5. Start API server:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run uvicorn app.main:app --reload --port 8000
```

6. Install frontend dependencies:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/frontend && npm install
```

7. Start Next.js dev server:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/frontend && npm run dev
```
