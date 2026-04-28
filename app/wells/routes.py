"""Wells endpoint with static mock well list."""

from datetime import date

from fastapi import APIRouter, Query


router = APIRouter(
    prefix="/api/v1",
    tags=["wells"],
)


@router.get("/wells")
def get_wells(
    date_query: date = Query(..., description="Fecha en formato YYYY-MM-DD")
) -> list[dict[str, str]]:
    """Return the available mock wells for the requested date."""
    date_query_str = date_query.strftime("%Y-%m-%d")
    print(f"Received request for wells on date: {date_query_str}")
    wells = ["POZO-001", "POZO-002", "POZO-003"]
    return [{"id_well": well_id} for well_id in wells]
