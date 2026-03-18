"""Shared FastAPI dependencies for request validation and authentication."""

from typing import Optional

from fastapi import Header, HTTPException


async def validate_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Validates the API key from the X-API-Key header.
    Returns 403 Forbidden if the key is invalid or missing.
    """
    valid_api_key = "abcdef12345"

    if not x_api_key or x_api_key != valid_api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

    return x_api_key
