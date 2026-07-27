"""
OAuth2DetectionStrategy — recognises OAuth 2.x from server responses.

Self-contained: performs RFC 9728 / RFC 8414 discovery directly
using the HttpClient port. Does not depend on OAuth2Strategy.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from mas.core.auth.discovery.detector import DetectionStrategy
from mas.core.auth.discovery.models import DetectionResult
from mas.core.auth.ports import HttpClient

logger = logging.getLogger(__name__)


class OAuth2DetectionStrategy(DetectionStrategy):

    async def detect(
        self,
        url: str,
        response_headers: Dict[str, str],
        http_client: HttpClient,
    ) -> Optional[DetectionResult]:
        prm = await self._fetch_protected_resource_metadata(url, response_headers, http_client)
        if prm is None:
            return None

        auth_servers = prm.get("authorization_servers", [])
        if not auth_servers:
            return None

        issuer = auth_servers[0].rstrip("/")
        as_meta = await self._fetch_as_metadata(issuer, http_client)
        if not as_meta:
            return None

        registration_endpoint = as_meta.get("registration_endpoint")

        return DetectionResult(
            protocol_type="oauth2",
            server_identifier=issuer,
            config={
                "authorization_endpoint": as_meta.get("authorization_endpoint", ""),
                "token_endpoint": as_meta.get("token_endpoint", ""),
                "scopes_supported": as_meta.get("scopes_supported", []),
                "resource_uri": prm.get("resource"),
                "issuer": issuer,
                **({"registration_endpoint": registration_endpoint} if registration_endpoint else {}),
            },
            needs_client_registration=registration_endpoint is None,
            scopes_supported=as_meta.get("scopes_supported", []),
            message=(
                "OAuth 2.0 authentication detected"
                if registration_endpoint
                else "OAuth 2.0 detected but dynamic registration not available"
            ),
        )

    # ------------------------------------------------------------------
    # RFC 9728 Protected Resource Metadata
    # ------------------------------------------------------------------

    @staticmethod
    async def _fetch_protected_resource_metadata(
        url: str,
        response_headers: Dict[str, str],
        http_client: HttpClient,
    ) -> Optional[Dict[str, Any]]:
        rm_url = OAuth2DetectionStrategy._extract_resource_metadata_url(response_headers)
        if rm_url:
            try:
                resp = await http_client.get(rm_url, timeout=5.0)
                if resp.status_code == 200 and resp.body:
                    return resp.body
            except Exception:
                pass

        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path_suffix = parsed.path.rstrip("/")

        for wk_url in [
            f"{base}/.well-known/oauth-protected-resource{path_suffix}",
            f"{base}/.well-known/oauth-protected-resource",
        ]:
            try:
                resp = await http_client.get(wk_url, timeout=5.0)
                if resp.status_code == 200 and resp.body:
                    return resp.body
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # RFC 8414 / OIDC Discovery
    # ------------------------------------------------------------------

    @staticmethod
    async def _fetch_as_metadata(
        issuer: str,
        http_client: HttpClient,
    ) -> Optional[Dict[str, Any]]:
        issuer = issuer.rstrip("/")
        parsed = urlparse(issuer)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")

        urls = [
            f"{origin}/.well-known/oauth-authorization-server{path}",
            f"{issuer}/.well-known/oauth-authorization-server",
            f"{origin}/.well-known/openid-configuration{path}",
            f"{issuer}/.well-known/openid-configuration",
        ]

        for url in urls:
            try:
                resp = await http_client.get(url, timeout=5.0)
                if resp.status_code == 200 and resp.body:
                    return resp.body
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_resource_metadata_url(headers: Dict[str, str]) -> Optional[str]:
        www_auth = headers.get("www-authenticate", headers.get("WWW-Authenticate", ""))
        if not www_auth:
            return None
        match = re.search(r'resource_metadata="([^"]+)"', www_auth)
        if match:
            return match.group(1)
        match = re.search(r"resource_metadata=(\S+)", www_auth)
        return match.group(1) if match else None
