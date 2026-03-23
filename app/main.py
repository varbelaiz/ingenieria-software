"""FastAPI application entry point and router registration."""

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.forecast import router as forecast_router  # noqa: E402
from app.middleware import ApiKeyMiddleware  # noqa: E402
from app.wells import router as wells_router  # noqa: E402

app = FastAPI(
    title="Plataforma Predictiva de Produccion",
    version="0.1.0",
)

app.add_middleware(ApiKeyMiddleware)

app.include_router(wells_router)
app.include_router(forecast_router)
