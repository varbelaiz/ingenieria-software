FROM python:3.10-slim AS base

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6.10 /uv /uvx /usr/local/bin/

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev group)
RUN uv sync --frozen --no-dev

# Copy application source
COPY app/ ./app/

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
