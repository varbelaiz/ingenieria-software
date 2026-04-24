# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the API (dev mode)
uv run uvicorn app.main:app --reload

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_forecast.py

# Run a single test
uv run pytest tests/test_forecast.py::test_name

# Run tests with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run all pre-commit hooks (black, flake8, pylint, mypy)
uv run pre-commit run --all-files

# Full local stack (API + Prometheus + Grafana)
docker compose up --build
```

## Architecture

The app is a FastAPI service (`app/`) with a Prometheus + Grafana monitoring stack and a Locust load testing runner (`load/`). Infrastructure lives in `infra/` as Terraform targeting AWS.

**Request lifecycle:** Every request passes through `ApiKeyMiddleware` (`app/middleware.py`) which validates the `X-API-Key` header, then delegates to the router, and records metrics post-response. Paths `/docs`, `/openapi.json`, `/healthz`, and `/metrics` bypass auth.

**Metrics:** `app/monitoring.py` owns three custom Prometheus metrics (`forecast_api_requests_total`, `forecast_api_errors_total`, `forecast_api_request_duration_seconds`) plus three process gauges. The middleware calls `observe_request()` after every instrumented response. The `/metrics` endpoint itself is excluded from instrumentation to avoid loops.

**Two environments:** Terraform workspaces `staging` (branch `develop`) and `prod` (branch `main`). CD runs via GitHub Actions → AWS SSM (no SSH). Secrets live in AWS Secrets Manager and are injected into `.env` at deploy time by `scripts/write_runtime_env.sh`.

**Grafana and Prometheus** are provisioned automatically from `grafana/provisioning/` and `grafana/dashboards/`. No manual setup needed locally or in prod.

## Code standards

- **Formatter:** Black (max line length 88). Config in `.pre-commit/.black.toml`.
- **Linter:** flake8 + pylint. Config in `.pre-commit/.flake8` and `.pre-commit/.pylintrc`.
- **Types:** mypy with `disallow_untyped_defs = True`. All functions must be fully typed.
- Pre-commit runs all four tools. CI enforces the same checks.

## Tests

Tests use `httpx.TestClient` against the FastAPI app. The `API_KEY` env var is set in `tests/conftest.py` via `tests.TEST_API_KEY = "abcdef12345"` — use that constant in any new test that needs auth headers.

```python
from tests import TEST_API_KEY
headers = {"X-API-Key": TEST_API_KEY}
```

## Key constraints

- The forecast model is mock/linear only: `max(base_value - 7.5 * day_index, 0)`. Valid wells: `POZO-001`, `POZO-002`, `POZO-003`.
- Locust is not part of `docker compose up`. Run it separately; see [`docs/load-testing.md`](docs/load-testing.md).
- Never commit `.env` or real secret values. Use `TF_VAR_*` for Terraform sensitive vars.
