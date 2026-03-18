"""FastAPI application entry point and router registration."""

from fastapi import FastAPI

from app.forecast import router as forecast_router
from app.wells import router as wells_router


app = FastAPI(
    title="Plataforma Predictiva de Produccion",
    version="0.1.0",
)

app.include_router(wells_router)
app.include_router(forecast_router)
