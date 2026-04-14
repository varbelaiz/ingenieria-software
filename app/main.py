"""FastAPI application entry point and router registration."""

from dotenv import load_dotenv
from fastapi import FastAPI

from app.forecast import router as forecast_router
from app.health import router as health_router
from app.middleware import ApiKeyMiddleware
from app.monitoring import router as monitoring_router
from app.wells import router as wells_router

load_dotenv()

app = FastAPI(
    title="Plataforma Predictiva de Produccion",
    version="0.1.0",
)

app.add_middleware(ApiKeyMiddleware)

app.include_router(wells_router)
app.include_router(forecast_router)
app.include_router(health_router)
app.include_router(monitoring_router)
