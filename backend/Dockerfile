# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

RUN groupadd --system appuser && useradd --system --gid appuser appuser

WORKDIR /app

# Copy virtualenv and source from builder
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/app ./app
COPY --from=builder /build/alembic ./alembic
COPY --from=builder /build/alembic.ini .

ENV PATH="/app/.venv/bin:$PATH"

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
