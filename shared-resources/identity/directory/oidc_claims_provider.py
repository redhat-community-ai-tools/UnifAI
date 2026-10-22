"""
OIDC claims directory provider.

Derives a user's groups from the claims of the access token issued by an
OpenID Connect provider (e.g. the ``groups`` claim emitted by Keycloak's
group-membership mapper) instead of querying an external directory.

Capabilities and limits
-----------------------
A token describes a single user, so this provider can only answer
questions about the *calling* user:

* ``get_user_groups`` / ``get_group`` / ``search_groups`` -- supported,
  limited to the groups carried by the current user's token.
* ``get_user`` -- supported for the current user only (built from claims).
* ``search_users`` -- NOT supported: the member list of a group or the
  user base cannot be enumerated from a token.  Returns ``[]`` and logs.
* ``DirectoryGroup.members`` is always empty.  ``group_members_authoritative``
  is ``False`` so callers must not overwrite stored member snapshots with it.

Group ids are the normalised claim values (see :func:`normalize_group`).
A team references such a group by that id (``type=group``, ``id=<name>``);
a user is a member when their token carries the group.

Security
--------
Groups are only ever read from a token whose signature, expiry and issuer
(and audience, when configured) were verified against the provider's JWKS
with PyJWT.  There is no unverified mode: ``jwks_url`` and ``issuer`` are
mandatory and the provider refuses to start without them.  Only asymmetric
algorithms (RS256, ES256) are accepted -- never ``none`` or HMAC.  Any
failure (bad signature, expired, wrong issuer, JWKS unreachable) fails
closed: no groups are returned and the reason is logged.
The token's username claim must match the user being queried, so a stale
token left on a shared provider instance can never grant another user's
groups.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, List, Optional

from directory.models import DirectoryGroup, DirectoryUser, OidcClaimsConfig
from directory.provider import DirectoryProvider

logger = logging.getLogger(__name__)

_ALLOWED_ALGORITHMS = ["RS256", "ES256"]
_JWKS_CACHE_SECONDS = 300


def normalize_group(
    raw: Any, *, prefix: str = "", lowercase: bool = False
) -> Optional[str]:
    """Normalise one raw claim value to a group id, or ``None`` if unusable.

    * surrounding whitespace is stripped;
    * leading ``/`` is stripped (Keycloak full group paths: ``/team`` -> ``team``;
      sub-groups keep inner separators: ``/a/b`` -> ``a/b``);
    * ``prefix`` is then removed when present;
    * case is preserved unless ``lowercase`` is true.
    """
    if not isinstance(raw, str):
        return None
    value = raw.strip().lstrip("/")
    if prefix and value.startswith(prefix):
        value = value[len(prefix):].lstrip("/")
    if lowercase:
        value = value.lower()
    return value or None


def _lookup(claims: dict, path: str) -> Any:
    """Exact key first (claim names may contain dots), then dotted path."""
    if path in claims:
        return claims[path]
    node: Any = claims
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


class OidcClaimsDirectoryProvider(DirectoryProvider):
    """Directory provider backed by the verified claims of a user token."""

    group_members_authoritative = False

    def __init__(self, config: OidcClaimsConfig):
        self._cfg = config
        self._local = threading.local()
        if not self._cfg.jwks_url or not self._cfg.issuer:
            raise ValueError(
                "oidc-claims requires jwks_url (DIRECTORY_OIDC_JWKS_URL) and "
                "issuer (DIRECTORY_OIDC_ISSUER): unverified tokens are never trusted"
            )
        import jwt  # PyJWT (already an identity dependency)
        # Keys are cached (set + per-kid) so a request does not hit the IdP.
        self._jwk_client = jwt.PyJWKClient(
            self._cfg.jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=_JWKS_CACHE_SECONDS,
            timeout=10,
        )

    # ── token handling ─────────────────────────────────────────────────

    def set_user_token(self, token: str) -> None:
        # Thread-local: the provider instance is shared across requests.
        self._local.token = token

    def _claims(self) -> dict:
        """Claims of the current token; ``{}`` when missing or invalid."""
        token = getattr(self._local, "token", None)
        if not token:
            logger.debug("oidc-claims: no user token set")
            return {}
        try:
            import jwt
            key = self._jwk_client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=_ALLOWED_ALGORITHMS,
                issuer=self._cfg.issuer,
                audience=self._cfg.audience or None,
                options={
                    "require": ["exp", "iss"],
                    "verify_aud": bool(self._cfg.audience),
                },
            )
        except Exception as exc:
            logger.warning("oidc-claims: token rejected (%s: %s)", type(exc).__name__, exc)
            return {}

    def _claims_for(self, user_id: str) -> dict:
        claims = self._claims()
        if not claims:
            return {}
        subject = claims.get(self._cfg.username_claim)
        if not user_id or subject != user_id:
            logger.warning(
                "oidc-claims: token subject does not match requested user; ignoring"
            )
            return {}
        return claims

    def _groups_from(self, claims: dict) -> List[str]:
        raw = _lookup(claims, self._cfg.claim)
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            logger.warning("oidc-claims: claim %r is not a list", self._cfg.claim)
            return []
        seen: List[str] = []
        for item in raw:
            gid = normalize_group(
                item, prefix=self._cfg.group_prefix, lowercase=self._cfg.lowercase
            )
            if gid and gid not in seen:
                seen.append(gid)
        return seen

    @staticmethod
    def _group(gid: str) -> DirectoryGroup:
        return DirectoryGroup(group_id=gid, name=gid)

    def _current_groups(self) -> List[str]:
        claims = self._claims()
        return self._groups_from(claims) if claims else []

    # ── users ──────────────────────────────────────────────────────────

    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        logger.info("oidc-claims: search_users is not supported (token-only provider)")
        return []

    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        claims = self._claims_for(user_id)
        if not claims:
            return None
        return DirectoryUser(
            user_id=user_id,
            username=user_id,
            display_name=str(claims.get("name") or user_id),
            email=str(claims.get("email") or ""),
        )

    # ── groups ─────────────────────────────────────────────────────────

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        """Groups of the *current* user whose id contains ``query``."""
        q = (query or "").strip().lower()
        found = [g for g in self._current_groups() if q in g.lower()]
        return [self._group(g) for g in found[:limit]] if limit else [
            self._group(g) for g in found
        ]

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        wanted = normalize_group(
            group_id, prefix=self._cfg.group_prefix, lowercase=self._cfg.lowercase
        )
        if wanted and wanted in self._current_groups():
            return self._group(wanted)
        return None

    def get_user_groups(self, user_id: str) -> List[DirectoryGroup]:
        claims = self._claims_for(user_id)
        return [self._group(g) for g in self._groups_from(claims)] if claims else []
