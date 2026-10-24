"""
Identity forwarding — present the acting user's identity to downstream gateways.

Some deployments put a policy gateway in front of models and tools (an
OpenAI-compatible model router, an MCP gateway) that authorizes, routes and
accounts per *human caller*, not per service.  For those, an element can opt
in to forwarding:

* ``forward_user_token`` — send the acting user's own OIDC access token as
  ``Authorization: Bearer …`` instead of a static API key.
* templated headers — header values rendered per call from the execution
  context, e.g. ``{"X-Session": "{session_id}", "X-Node": "{node_uid}"}``.

Security model: no token is ever written to MongoDB, the session record or
Temporal history.  At submission time the HTTP layer records a short-lived
*binding* (MAS session id → identity server-session id) next to the identity
sessions themselves; the token is resolved just in time from that binding and
refreshed when close to expiry.  Forwarding fails closed: when no valid user
token can be resolved the call raises instead of falling back to anonymous.
"""
from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from mas.core.auth.target_policy import forwarding_target_allowed
from mas.core.execution_context import SESSION_TAGS_TAG, ExecutionContextHolder

logger = logging.getLogger(__name__)

#: ``auth_method`` value that presents the acting user's own platform token to a downstream server.
FORWARD_USER_TOKEN = "forward_user_token"


class IdentityTokenUnavailable(RuntimeError):
    """No valid user token can be resolved for the running session."""


# ──────────────────────────────────────────────────────────────────────────────
# Current node (set by BaseNode around each node run)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NodeIdentity:
    uid: str = ""
    display_name: str = ""
    node_type: str = ""


_NO_NODE = NodeIdentity()
_CURRENT_NODE: ContextVar[NodeIdentity | None] = ContextVar("mas_current_node", default=None)


@contextmanager
def bind_current_node(uid: str, display_name: str = "", node_type: str = "") -> Iterator[None]:
    token = _CURRENT_NODE.set(NodeIdentity(uid=uid or "", display_name=display_name or "", node_type=node_type or ""))
    try:
        yield
    finally:
        _CURRENT_NODE.reset(token)


def current_node() -> NodeIdentity:
    return _CURRENT_NODE.get() or _NO_NODE


# ──────────────────────────────────────────────────────────────────────────────
# Token source port
# ──────────────────────────────────────────────────────────────────────────────

class IdentityTokenSource(ABC):
    """Resolves the acting user's access token for a running MAS session."""

    @abstractmethod
    def bind(self, session_id: str, identity_session_id: str, username: str) -> None:
        """Record which identity server-session acts for ``session_id``."""

    @abstractmethod
    def get_access_token(self, session_id: str, username: str) -> str:
        """Return a valid access token or raise :class:`IdentityTokenUnavailable`.

        ``username`` is the credential user the execution context names; a
        binding recorded for another user is refused.
        """


class NullIdentityTokenSource(IdentityTokenSource):
    """Used when forwarding is not configured: binding is a no-op, lookups fail closed."""

    def bind(self, session_id: str, identity_session_id: str, username: str) -> None:
        return None

    def get_access_token(self, session_id: str, username: str) -> str:
        raise IdentityTokenUnavailable("identity forwarding is not configured on this MAS instance")


# ──────────────────────────────────────────────────────────────────────────────
# Header templates
# ──────────────────────────────────────────────────────────────────────────────

_PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.\-]+)\}")


def render_header_templates(
    templates: Mapping[str, Any],
    variables: Mapping[str, str],
) -> dict[str, str]:
    """Render ``{name}`` placeholders in header values.

    A header whose template references an unknown or empty variable is
    omitted rather than sent with a partial value — a missing classification
    must never be forwarded as an empty string a gateway could misread.
    Values without placeholders pass through unchanged.
    """
    rendered: dict[str, str] = {}
    for name, raw in (templates or {}).items():
        if raw is None:
            continue
        template = str(raw)
        missing = False

        def _sub(match: re.Match[str]) -> str:
            nonlocal missing
            value = variables.get(match.group(1), "")
            if value in (None, ""):
                missing = True
                return ""
            return str(value)

        value = _PLACEHOLDER.sub(_sub, template)
        if missing:
            logger.debug("Header %s omitted: template %r has an unresolved variable", name, template)
            continue
        rendered[str(name)] = value
    return rendered


# ──────────────────────────────────────────────────────────────────────────────
# Forwarder (bound per session at build time)
# ──────────────────────────────────────────────────────────────────────────────

class IdentityForwarder:
    """Builds forwarded headers for the session an element runs in.

    Template variables:

    ``session_id``, ``user`` (acting human), ``identity`` / ``identity_type``
    (workspace owner: user or team), ``scope``, ``node_uid``, ``node_name``,
    ``node_type``, and ``tag.<key>`` for every session metadata tag stamped at
    submission (see :data:`SESSION_TAGS_TAG`).
    """

    def __init__(
        self,
        token_source: IdentityTokenSource,
        ctx_holder: ExecutionContextHolder | None,
        target_urls: tuple[str, ...] | None = None,
    ) -> None:
        self._source = token_source
        self._holder = ctx_holder
        # URLs the forwarded token may reach. ``None`` = not restricted (header templates only).
        self._targets = target_urls

    def variables(self) -> dict[str, str]:
        out: dict[str, str] = {}
        node = current_node()
        out["node_uid"] = node.uid
        out["node_name"] = node.display_name
        out["node_type"] = node.node_type
        if self._holder is None:
            return out
        try:
            ctx = self._holder.context
        except RuntimeError:
            return out
        out["session_id"] = ctx.session_id
        out["user"] = ctx.credential_user_id()
        out["identity"] = ctx.identity.id
        out["identity_type"] = "team" if ctx.identity.is_team else "user"
        out["scope"] = ctx.scope
        tags = ctx.tags or {}
        for key, value in (tags.get(SESSION_TAGS_TAG) or {}).items():
            out[f"tag.{key}"] = "" if value is None else str(value)
        return out

    def access_token(self) -> str:
        if self._targets is not None and not all(forwarding_target_allowed(u) for u in self._targets):
            raise IdentityTokenUnavailable(
                "the user token is only forwarded to cluster-internal or allow-listed servers"
            )
        if self._holder is None:
            raise IdentityTokenUnavailable("no execution context bound to this element")
        try:
            ctx = self._holder.context
        except RuntimeError as exc:
            raise IdentityTokenUnavailable(str(exc)) from exc
        user = ctx.credential_user_id()
        if not ctx.session_id or not user:
            raise IdentityTokenUnavailable(
                "the running session has no acting user (team sessions need a credential user)"
            )
        return self._source.get_access_token(ctx.session_id, user)

    def headers(self, templates: Mapping[str, Any] | None = None, forward_token: bool = False) -> dict[str, str]:
        out = render_header_templates(templates or {}, self.variables())
        if forward_token:
            out["Authorization"] = f"Bearer {self.access_token()}"
        return out


class ForwardedIdentityCredential:
    """:class:`~mas.core.auth.credentials.credential.AuthCredential` backed by the acting user.

    Lets MCP providers (or any consumer of the credential protocol) present
    the user's own token, refreshed by the token source, with no stored
    per-server credential.
    """

    def __init__(
        self,
        forwarder: IdentityForwarder,
        header_templates: Mapping[str, Any] | None = None,
        target_url: str = "",
    ) -> None:
        self._forwarder = forwarder
        self._templates = dict(header_templates or {})
        self._target_url = target_url

    def _check_target(self) -> None:
        """The platform token goes only to cluster-internal or allow-listed servers (fail closed)."""
        if not forwarding_target_allowed(self._target_url):
            raise IdentityTokenUnavailable(
                "the user token is only forwarded to cluster-internal or allow-listed servers"
            )

    async def get_headers(self) -> dict[str, str]:
        self._check_target()
        return await asyncio.to_thread(self._forwarder.headers, self._templates, True)

    async def get_token(self) -> str:
        self._check_target()
        return await asyncio.to_thread(self._forwarder.access_token)

    async def attempt_recovery(self):
        from mas.core.auth.credentials.models import RecoveryResult
        try:
            await self.get_token()
        except IdentityTokenUnavailable as exc:
            return RecoveryResult(recovered=False, should_retry=False, reason=str(exc))
        return RecoveryResult(recovered=True, should_retry=True, reason="user token re-resolved")
