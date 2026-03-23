"""Global middleware for request-level concerns."""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

API_KEY = os.environ["API_KEY"]


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates the X-API-Key header on every incoming request."""

    async def dispatch(self, request: Request, call_next):
        api_key = request.headers.get("X-API-Key")

        if api_key != API_KEY:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)