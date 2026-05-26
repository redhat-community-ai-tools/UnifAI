"""Base HTTP client for the MAS API."""
from __future__ import annotations

from typing import Any, Optional

import requests

from unifai_cli.config.app_config import AppConfig

AUTH_USER_HEADER = "X-Authenticated-User"


class MASClient:
    """HTTP primitives for the MAS (Multi-Agent System) API."""

    def __init__(self, base_url: str):
        config = AppConfig.get_instance()
        self.base_url = base_url.rstrip("/")
        self.api_prefix = config.api_prefix
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._authenticated_user: Optional[str] = None

    def set_authenticated_user(self, user_id: str) -> None:
        """Set the default user for auth headers and identity on session APIs."""
        self._authenticated_user = user_id

    def _effective_user_id(self, user_id: Optional[str] = None) -> Optional[str]:
        return user_id or self._authenticated_user

    def _url(self, parent: str, route: str) -> str:
        return f"{self.base_url}{self.api_prefix}/{parent}/{route}"

    def _auth_headers(self, user_id: Optional[str] = None) -> dict[str, str]:
        uid = self._effective_user_id(user_id)
        if not uid:
            return {}
        return {AUTH_USER_HEADER: uid}

    def _get(self, parent: str, route: str, params: dict = None,
             user_id: Optional[str] = None) -> Any:
        resp = self.session.get(
            self._url(parent, route),
            params=params,
            headers=self._auth_headers(user_id),
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, parent: str, route: str, json: dict = None,
              user_id: Optional[str] = None) -> Any:
        resp = self.session.post(
            self._url(parent, route),
            json=json,
            headers=self._auth_headers(user_id),
        )
        resp.raise_for_status()
        return resp.json()

    def _post_stream(self, parent: str, route: str, json: dict = None,
                     user_id: Optional[str] = None):
        """POST with NDJSON streaming response."""
        resp = self.session.post(
            self._url(parent, route),
            json=json,
            stream=True,
            headers=self._auth_headers(user_id),
        )
        resp.raise_for_status()
        return resp

    def _get_stream(self, parent: str, route: str, params: dict = None,
                    user_id: Optional[str] = None):
        """GET with NDJSON streaming response."""
        resp = self.session.get(
            self._url(parent, route),
            params=params,
            stream=True,
            headers=self._auth_headers(user_id),
        )
        resp.raise_for_status()
        return resp

    def _delete(self, parent: str, route: str, params: dict = None,
                user_id: Optional[str] = None) -> Any:
        resp = self.session.delete(
            self._url(parent, route),
            params=params,
            headers=self._auth_headers(user_id),
        )
        resp.raise_for_status()
        return resp.json()
