"""Technical endpoints for runtime health checks."""

from fastapi import APIRouter


router = APIRouter(include_in_schema=False)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Return a minimal health payload for infrastructure checks."""
    return {"status": "ok"}
