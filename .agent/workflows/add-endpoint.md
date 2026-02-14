---
description: how to add a new API endpoint
---

## Steps

1. **Create or edit the route file** in `backend/app/api/routes/`. Each domain gets its own file (e.g., `library.py`, `judge.py`).

2. **Define Pydantic schemas** for request and response bodies in the route file or in `backend/app/models/schemas.py`:
   - Request models for POST/PUT/PATCH bodies
   - Response models for all endpoints
   - Use `Field(...)` for validation constraints

3. **Add the route** using `APIRouter()`:
   - Use appropriate HTTP method and status code
   - Include `Depends(get_current_user)` for auth
   - Include response_model for type safety
   - Add docstring for OpenAPI docs

4. **Register the router** in `backend/app/main.py`:

   ```python
   from app.api.routes import new_module
   app.include_router(new_module.router, prefix="/api/v1", tags=["new_module"])
   ```

5. **Write tests** in `backend/tests/unit/test_new_module.py`:
   - Test happy path
   - Test validation errors
   - Test auth required
   - Test tenant isolation (can't access other user's data)

6. **Run tests**:
   ```bash
   cd /Users/kasey.kaplan/Documents/kk-projects/arbiter-ai/backend && uv run pytest tests/ -v -k test_new_module
   ```
