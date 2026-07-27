"""
API-key-specific configuration.
"""

from __future__ import annotations

from pydantic import BaseModel


class ApiKeyConfig(BaseModel):
    """How the API key should be sent in HTTP requests."""
    header_name: str = "Authorization"
    header_prefix: str = "Bearer "
