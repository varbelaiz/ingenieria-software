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
) -> dict[str, object]:
    """Return the available mock wells for the requested date."""
    wells = ["POZO-001", "POZO-002", "POZO-003"]
    return {
        "date_query": date_query.isoformat(),
        "wells": wells,
    }
