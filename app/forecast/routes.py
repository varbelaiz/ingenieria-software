from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import validate_api_key


router = APIRouter(
    prefix="/api/v1",
    tags=["forecast"],
    dependencies=[Depends(validate_api_key)],
)

BASE_PRODUCTION_BY_WELL = {
    "POZO-001": 1200.0,
    "POZO-002": 980.0,
    "POZO-003": 760.0,
}


@router.get("/forecast")
def get_forecast(
    id_well: str = Query(..., description="Identificador del pozo"),
    date_start: date = Query(..., description="Fecha inicial YYYY-MM-DD"),
    date_end: date = Query(..., description="Fecha final YYYY-MM-DD"),
):
    if id_well not in BASE_PRODUCTION_BY_WELL:
        raise HTTPException(status_code=404, detail="Pozo no encontrado")

    if date_end < date_start:
        raise HTTPException(status_code=400, detail="date_end debe ser mayor o igual a date_start")

    days = (date_end - date_start).days + 1
    base_value = BASE_PRODUCTION_BY_WELL[id_well]
    decline_per_day = 7.5

    series = []
    for day_index in range(days):
        current_date = date_start + timedelta(days=day_index)
        production = max(base_value - (decline_per_day * day_index), 0)
        series.append(
            {
                "date": current_date.isoformat(),
                "oil_bopd": round(production, 2),
            }
        )

    return {
        "id_well": id_well,
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
        "trend": "linear_decreasing",
        "data": series,
    }