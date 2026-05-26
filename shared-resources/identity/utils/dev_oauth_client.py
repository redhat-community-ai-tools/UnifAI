"""Dev-only OAuth client that replaces Keycloak for local development."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from flask import redirect
from werkzeug.wrappers import Response


class DevOAuthClient:
    """Drop-in replacement for the Authlib OAuth client in local auth mode.

    Returns hardcoded dev-user responses so the full auth flow
    (login -> redirect -> callback -> session) runs through real code paths.
    """

    def authorize_redirect(self, redirect_uri: str, **kwargs: Any) -> Response:
        state = kwargs.get("state", "")
        return redirect(f"{redirect_uri}?code=dev-code&state={state}")

    def authorize_access_token(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "access_token": str(uuid.uuid4()),
            "refresh_token": "dev-refresh-token",
            "expires_at": (datetime.now() + timedelta(hours=10)).timestamp(),
        }

    def userinfo(self, **kwargs: Any) -> dict[str, str]:
        return {
            "preferred_username": "dev-user",
            "email": "dev@local.dev",
            "name": "Dev User",
            "sub": "local:dev-user",
        }

    def fetch_access_token(self, **kwargs: Any) -> dict[str, Any]:
        return self.authorize_access_token()
