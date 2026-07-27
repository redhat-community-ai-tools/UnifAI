"""
Detection result — protocol-agnostic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DetectionResult(BaseModel):
    """Result of probing a server's auth requirements."""
    protocol_type: str
    server_identifier: str = Field(
        default="",
        description="Auth server issuer (e.g. https://accounts.google.com)",
    )
    config: Dict[str, Any] = Field(default_factory=dict)
    needs_client_registration: bool = False
    scopes_supported: List[str] = Field(default_factory=list)
    message: Optional[str] = None
