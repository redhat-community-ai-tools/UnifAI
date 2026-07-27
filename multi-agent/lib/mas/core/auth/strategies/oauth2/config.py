"""
OAuth2-specific configuration value object.

This is the *scheme-level* config — what the OAuth2 adapter needs to
operate.  It is derived from an auth element's stored config at runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OAuth2Config(BaseModel):
    """Everything the OAuth 2.x scheme layer needs."""
    client_id: str
    client_secret: Optional[str] = None
    authorization_endpoint: str
    token_endpoint: str
    token_endpoint_auth_method: str = "client_secret_post"
    scopes: List[str] = Field(default_factory=list)
    resource_uri: Optional[str] = None
    extra_authorize_params: Dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> OAuth2Config:
        """Build from a raw config dict (tolerant of extra keys)."""
        return cls.model_validate(raw)
