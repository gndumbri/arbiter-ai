---
description: code quality rules and conventions for the arbiter-ai project
---

## Project Conventions

### Python (Backend)

- **Python 3.12+** with type hints on all function signatures
- **FastAPI** for all API endpoints
- **SQLAlchemy 2.0** async style for database queries
- **Pydantic v2** models for all request/response schemas
- **`structlog`** for all logging (JSON format, correlation IDs)
- Private functions prefixed with `_`, not exported
- All DB queries must include `user_id` filter for tenant isolation
- Never use `SELECT *`. Be explicit about columns.

### Naming

- Files: `snake_case.py` / `PascalCase.tsx`
- Python: `snake_case` functions/variables, `PascalCase` classes
- TypeScript: `camelCase` functions/variables, `PascalCase` components
- API routes: `/api/v1/{resource}` (plural nouns)
- Pinecone namespaces: `user_{uuid}` or `official_{slug}_{slug}`

### Security

- Every endpoint (except `/health`) requires auth
- Publisher endpoints use API key auth (`X-Publisher-Key`)
- All file uploads go to quarantine first — never process directly
- All SQL queries must be parameterized (no f-strings with SQL)
- Input sanitization: strip HTML/script, limit query length to 500 chars
- Never log sensitive data (API keys, tokens, PII)

### Error Handling

- All errors return consistent JSON: `{ "error": { "code": "...", "message": "..." } }`
- Use specific error codes: `VALIDATION_ERROR`, `UNAUTHORIZED`, `RATE_LIMITED`, `SESSION_EXPIRED`, `NOT_A_RULEBOOK`, `BLOCKED_FILE`
- Never expose stack traces in production responses

### Testing

- Every new module must have corresponding unit tests
- Integration tests for all API endpoints
- Test fixtures in `tests/fixtures/`
- Use `pytest` with `pytest-asyncio` for async tests

### Git

- Branch: work on `kk-branch`
- Commit messages: `type: description` (e.g., `feat: add ingestion pipeline`, `fix: handle multi-column PDFs`)
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
