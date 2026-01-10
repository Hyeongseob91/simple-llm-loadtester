"""Authentication middleware for API key validation."""

import os
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader

# API Key configuration
API_KEY_HEADER_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def get_api_key_from_env() -> Optional[str]:
    """Get API key from environment variable."""
    return os.getenv("API_KEY")


async def verify_api_key(request: Request, api_key: Optional[str] = None) -> bool:
    """Verify API key from request header.

    Args:
        request: FastAPI request object.
        api_key: API key from header (optional).

    Returns:
        True if authentication is disabled or key is valid.

    Raises:
        HTTPException: If authentication is required and key is invalid.
    """
    expected_key = get_api_key_from_env()

    # If no API key is configured, authentication is disabled
    if not expected_key:
        return True

    # Extract API key from header
    if not api_key:
        api_key = request.headers.get(API_KEY_HEADER_NAME)

    # Verify API key
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return True


class APIKeyAuth:
    """Dependency for API key authentication."""

    def __init__(self, required: bool = True):
        """Initialize API key auth dependency.

        Args:
            required: Whether authentication is required for this endpoint.
        """
        self.required = required

    async def __call__(self, request: Request) -> bool:
        """Validate API key.

        Args:
            request: FastAPI request object.

        Returns:
            True if authenticated or authentication is not required.

        Raises:
            HTTPException: If authentication fails.
        """
        expected_key = get_api_key_from_env()

        # If authentication is not configured, skip validation
        if not expected_key:
            return True

        # If authentication is not required for this endpoint, skip validation
        if not self.required:
            return True

        # Extract and verify API key
        api_key = request.headers.get(API_KEY_HEADER_NAME)
        return await verify_api_key(request, api_key)
