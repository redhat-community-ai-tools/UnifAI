"""Base HTTP client for the MAS API.

Authentication is done via a ``session`` cookie.  The Identity service signs
the cookie during CLI SSO login and returns it ready to use — the CLI stores
and sends it as-is without needing the SECRET_KEY.
"""
from __future__ import annotations

from typing import Any, Optional

import requests

from unifai_cli.config.app_config import AppConfig


class MASClient:
    """HTTP primitives for the MAS (Multi-Agent System) API."""

    def __init__(self, base_url: str):
        config = AppConfig.get_instance()
        self.base_url = base_url.rstrip("/")
        self.api_prefix = config.api_prefix
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def set_session_cookie(self, session_cookie: str) -> None:
        """Install the pre-signed session cookie on the requests.Session."""
        self.session.cookies.set("session", session_cookie)


    def _url(self, parent: str, route: str) -> str:
        return f"{self.base_url}{self.api_prefix}/{parent}/{route}"

    def _get(self, parent: str, route: str, params: Optional[dict] = None) -> Any:
        resp = self.session.get(
            self._url(parent, route),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, parent: str, route: str, json: Optional[dict] = None) -> Any:
        resp = self.session.post(
            self._url(parent, route),
            json=json,
        )
        resp.raise_for_status()
        return resp.json()

    def _post_stream(self, parent: str, route: str, json: Optional[dict] = None) -> requests.Response:
        """POST with NDJSON streaming response."""
        resp = self.session.post(
            self._url(parent, route),
            json=json,
            stream=True,
        )
        resp.raise_for_status()
        return resp

    def _get_stream(self, parent: str, route: str, params: Optional[dict] = None) -> requests.Response:
        """GET with NDJSON streaming response."""
        resp = self.session.get(
            self._url(parent, route),
            params=params,
            stream=True,
        )
        resp.raise_for_status()
        return resp

    def _delete(self, parent: str, route: str, params: Optional[dict] = None) -> Any:
        resp = self.session.delete(
            self._url(parent, route),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
