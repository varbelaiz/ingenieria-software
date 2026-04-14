FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv
RUN python -m venv /opt/venv

COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
