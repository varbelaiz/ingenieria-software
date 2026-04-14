"""Global middleware for request-level concerns."""

import os
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.monitoring import observe_request, start_timer


# Pylint flags this Starlette middleware shape, but it is expected here.
# pylint: disable=too-few-public-methods
class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates the X-API-Key header on every incoming request."""

    EXCLUDED_PATHS = {"/docs", "/openapi.json", "/metrics", "/healthz"}
    NON_INSTRUMENTED_PATHS = {"/metrics", "/healthz"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started_at = start_timer()
        path = request.url.path
        api_key_configured = os.getenv("API_KEY")

        if path in self.EXCLUDED_PATHS:
            response = await call_next(request)
            if path in self.NON_INSTRUMENTED_PATHS:
                return response
            observe_request(
                request.method,
                path,
                response.status_code,
                started_at,
            )
            return response

        if not api_key_configured:
            response = JSONResponse(
                status_code=500,
                content={"detail": "API_KEY is not configured"},
            )
            observe_request(
                request.method,
                path,
                response.status_code,
                started_at,
            )
            return response

        api_key = request.headers.get("X-API-Key")

        if api_key != api_key_configured:
            response = JSONResponse(
                status_code=403,
                content={"detail": "Invalid or missing API key"},
            )
            observe_request(
                request.method,
                path,
                response.status_code,
                started_at,
            )
            return response

        try:
            response = await call_next(request)
        except Exception:
            observe_request(request.method, path, 500, started_at)
            raise

        observe_request(
            request.method,
            path,
            response.status_code,
            started_at,
        )
        return response
