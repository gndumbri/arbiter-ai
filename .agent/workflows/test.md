---
description: how to run all tests
---

// turbo-all

## Steps

1. Run backend unit tests:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run pytest tests/unit/ -v
```

2. Run backend integration tests:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run pytest tests/integration/ -v
```

3. Run backend type checking:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run mypy app/ --ignore-missing-imports
```

4. Run backend linting:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run ruff check app/
```

5. Run frontend type checking:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/frontend && npx tsc --noEmit
```

6. Run frontend linting:

```bash
cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/frontend && npm run lint
```
