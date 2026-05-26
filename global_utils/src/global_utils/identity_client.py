"""
Shared HTTP client for the Identity pod's REST API.

Consolidates all HTTP communication with the Identity pod (teams + directory
endpoints) so that consumers (MAS, decorators, any future service) go through
a single client instead of making raw ``requests.get`` calls inline.

The Identity pod (``shared-resources/identity/``) owns the actual LDAP logic;
this module never touches LDAP directly — it only speaks HTTP to the pod.
"""
import logging
import time
from threading import Lock
from typing import Optional

import requests as http_requests

logger = logging.getLogger(__name__)

_TEAM_CACHE_TTL_SEC = 45.0


class IdentityClient:
    """HTTP client for the Identity pod (teams + directory APIs).

    Args:
        base_url: Root URL of the Identity pod (e.g. ``http://identity:13456``).
        timeout: Default HTTP timeout in seconds for all requests.
    """

    def __init__(self, base_url: str, timeout: int = 5):
        self._base = (base_url or "").rstrip("/")
        self._timeout = timeout
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        self._cache_lock = Lock()

    @property
    def configured(self) -> bool:
        """True when a non-empty base URL was provided."""
        return bool(self._base)

    # ── Team cache internals ──────────────────────────────────────────

    def _get_cached_teams(self, username: str) -> Optional[list[dict]]:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(username)
            if entry is not None and (now - entry[0]) < _TEAM_CACHE_TTL_SEC:
                return entry[1]
        return None

    def _set_cached_teams(self, username: str, teams: list[dict]) -> None:
        with self._cache_lock:
            self._cache[username] = (time.monotonic(), teams)

    def _invalidate_cached_teams(self, username: str) -> None:
        with self._cache_lock:
            self._cache.pop(username, None)

    # ── Teams API ─────────────────────────────────────────────────────

    def list_teams_for_user(self, username: str) -> list[dict]:
        """Return the raw ``teams`` array from Identity ``teams.list``.

        Raises on non-2xx responses.
        """
        resp = http_requests.get(
            f"{self._base}/api/teams/teams.list",
            params={"userId": username},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("teams", []) or []

    def _teams_for_user_cached(self, username: str) -> list[dict]:
        """Return teams (cached).  Raises on HTTP errors."""
        cached = self._get_cached_teams(username)
        if cached is not None:
            return cached
        teams = self.list_teams_for_user(username)
        self._set_cached_teams(username, teams)
        return teams

    def get_team_ids(self, username: str) -> frozenset[str]:
        """Team IDs the user belongs to (cached, never raises)."""
        if not self._base:
            return frozenset()
        try:
            teams = self._teams_for_user_cached(username)
            return frozenset(
                str(t.get("team_id"))
                for t in teams
                if t.get("team_id") is not None
            )
        except Exception:
            logger.exception("IdentityClient.get_team_ids failed for %s", username)
            return frozenset()

    def is_member(self, username: str, team_id: str) -> bool:
        """Check team membership.

        Fails **open** (returns ``True``) when not configured so local-dev
        works without an Identity pod.  When configured, checks cached team
        IDs first; on a cache miss (team not found), invalidates the cache
        and retries with a fresh HTTP call so that newly-created teams are
        recognised immediately instead of waiting for the cache TTL.
        """
        if not self._base:
            return True
        team_ids = self.get_team_ids(username)
        if team_id in team_ids:
            return True
        self._invalidate_cached_teams(username)
        return team_id in self.get_team_ids(username)

    def resolve_team_id(
        self, username: str, team_name_or_id: str,
    ) -> Optional[str]:
        """Map a team display-name or ID to its canonical ``team_id``.

        Returns the raw value when not configured (legacy/local-dev).
        Returns ``None`` when configured but no matching team is found.
        """
        raw = str(team_name_or_id).strip()
        if not raw:
            return None
        if not self._base:
            return raw
        try:
            teams = self._teams_for_user_cached(username)
        except Exception:
            logger.exception("IdentityClient.resolve_team_id failed for %s", username)
            return None

        for t in teams:
            tid = str(t.get("team_id") or "").strip()
            if not tid:
                continue
            if raw.casefold() == tid.casefold():
                return tid
            nm = str(t.get("name") or "").strip()
            if nm and raw.casefold() == nm.casefold():
                return tid
        return None

    def resolve_team_display_name(self, username: str, team_id: str) -> str:
        """Return the display name for *team_id*, falling back to *team_id* itself."""
        if not self._base:
            return team_id
        try:
            teams = self._teams_for_user_cached(username)
        except Exception:
            logger.exception(
                "IdentityClient.resolve_team_display_name failed for %s", username,
            )
            return team_id

        for t in teams:
            tid = str(t.get("team_id") or "").strip()
            if tid and tid.casefold() == team_id.casefold():
                return str(t.get("name") or "") or team_id
        return team_id

    # ── Directory API ─────────────────────────────────────────────────

    def _directory_headers(self, token: Optional[str] = None) -> dict:
        h: dict = {}
        if token:
            h["X-User-Token"] = token
        return h

    def search_directory(
        self,
        query: str,
        limit: int = 10,
        token: Optional[str] = None,
    ) -> list[dict]:
        """Search users via the Identity directory endpoint."""
        resp = http_requests.get(
            f"{self._base}/api/directory/directory.search_users",
            params={"q": query, "limit": limit},
            headers=self._directory_headers(token),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("users", [])

    def get_user(
        self,
        user_id: str,
        token: Optional[str] = None,
    ) -> Optional[dict]:
        """Fetch a single user from the Identity directory.

        Returns ``None`` for 404.  Raises on other non-2xx.
        """
        resp = http_requests.get(
            f"{self._base}/api/directory/directory.get_user",
            params={"userId": user_id},
            headers=self._directory_headers(token),
            timeout=self._timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def search_groups(
        self,
        query: str,
        limit: int = 20,
        token: Optional[str] = None,
    ) -> list[dict]:
        """Search groups via the Identity directory endpoint."""
        resp = http_requests.get(
            f"{self._base}/api/directory/directory.search_groups",
            params={"q": query, "limit": limit},
            headers=self._directory_headers(token),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("groups", [])

    def get_group(
        self,
        group_id: str,
        token: Optional[str] = None,
    ) -> Optional[dict]:
        """Fetch a single group from the Identity directory.

        Returns ``None`` for 404.  Raises on other non-2xx.
        """
        resp = http_requests.get(
            f"{self._base}/api/directory/directory.get_group",
            params={"groupId": group_id},
            headers=self._directory_headers(token),
            timeout=self._timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
