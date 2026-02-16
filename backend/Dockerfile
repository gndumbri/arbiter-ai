# ── Stage 1: Install dependencies ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

# WHY: uv is much faster than pip for dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install production dependencies only (no dev extras)
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Add venv to PATH so `python` resolves to the venv python
ENV PATH="/app/.venv/bin:$PATH"
# WHY: Prevents Python from buffering stdout/stderr, so logs appear immediately
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check against the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# WHY: Run Alembic migrations before starting the server so the database
# schema is always up to date on deploy (same pattern as Django's migrate).
# Safe with a single task; if scaling to multiple tasks, move migrations
# to a dedicated one-off ECS task in the CI/CD pipeline instead.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
