"""
AuthCredential — the ONLY interface that auth consumers depend on.

MCP providers, tools, and any element that needs authenticated HTTP
calls depends on this protocol — never on scheme specifics.

All methods are async because credential operations may involve I/O
(e.g. token refresh via HTTP).
"""

from __future__ import annotations

from typing import Dict, Protocol, runtime_checkable

from .models import RecoveryResult


@runtime_checkable
class AuthCredential(Protocol):
    """Minimal contract for presenting credentials in HTTP requests."""

    async def get_headers(self) -> Dict[str, str]:
        """Return HTTP headers (e.g. ``{"Authorization": "Bearer …"}``)."""
        ...

    async def get_token(self) -> str:
        """Return the raw access token / API key string."""
        ...

    async def attempt_recovery(self) -> RecoveryResult:
        """Credential was rejected. Try to self-heal.

        Returns a RecoveryResult so the caller knows whether to retry.
        """
        ...
