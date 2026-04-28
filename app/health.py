"""Technical endpoints for runtime health checks."""

from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Return a minimal health payload for infrastructure checks."""
    return {"status": "ok"}
