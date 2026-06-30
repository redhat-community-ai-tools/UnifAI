"""
CLI bootstrap — build the API client and resolve the session.

Configuration lives in ``unifai_cli.config.app_config``.
API methods live in ``unifai_cli.api``.
Auth session lives in ``unifai_cli.auth``.
"""
from __future__ import annotations

import os
from typing import Optional

from unifai_cli.api.base import MASClient
from unifai_cli.api.blueprints import BlueprintsAPI
from unifai_cli.api.resources import ResourcesAPI
from unifai_cli.api.sessions import SessionsAPI
from unifai_cli.config.app_config import AppConfig


class _UnifAIClient(BlueprintsAPI, ResourcesAPI, SessionsAPI):
    """Composite client with blueprints, resources, and sessions capabilities."""


def build_client(
    mas_url: Optional[str] = None,
    session_cookie: Optional[str] = None,
) -> MASClient:
    """Build a MAS API client from URL flag or environment.

    The client authenticates via the session cookie — MAS validates
    the caller server-side using the Redis session store.
    """
    config = AppConfig.get_instance()
    url = mas_url or os.environ.get("MAS_URL", config.mas_url)
    client = _UnifAIClient(url)
    if session_cookie:
        client.set_session_cookie(session_cookie)
    return client


def resolve_session() -> str:
    """Resolve the session cookie for API authentication.

    Returns:
        The session cookie string.

    Flow:
      1. Local SSO session (``~/.unifai/session.json``, 10-hour TTL)
      2. Browser-based SSO login (triggers automatically when no session exists)

    Raises:
        SystemExit(1) if authentication fails.
    """
    from unifai_cli.auth.flow import ensure_authenticated
    session = ensure_authenticated()
    cookie = session.get("session_cookie")
    if not cookie:
        from rich.console import Console
        Console().print("[red]Session cookie missing. Run [bold]unifai auth login --force[/bold] to re-authenticate.[/red]")
        raise SystemExit(1)
    return cookie
