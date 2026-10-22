"""Scope access control of the memory tool.

The acting user is always resolved from the execution context of the running
session, never from tool arguments. Every check fails closed: a missing
identity, an identity provider error or a non-member is a refusal.
"""
import logging
from typing import Any, Callable, Optional

from mas.core.execution_context import ExecutionContextHolder
from mas.core.identity.ports import IdentityProvider
from .config import AccessMode

logger = logging.getLogger(__name__)


ACCESS_REFUSED_PREFIX = "memory access refused"


class ScopeAccessDenied(Exception):
    """The acting user may not use the scope. The message is safe to show to the model."""


def acting_user(holder: Optional[ExecutionContextHolder]) -> str:
    """Return the acting user id from the execution context, or raise ``ScopeAccessDenied``."""
    if holder is None:
        raise ScopeAccessDenied(f"{ACCESS_REFUSED_PREFIX}: no execution context is bound")
    try:
        user = holder.context.credential_user_id()
    except RuntimeError:
        raise ScopeAccessDenied(f"{ACCESS_REFUSED_PREFIX}: no execution context is bound") from None
    user = (user or "").strip()
    if not user:
        raise ScopeAccessDenied(f"{ACCESS_REFUSED_PREFIX}: the acting user cannot be identified")
    return user


class TeamScopeAccessChecker:
    """``scope_id`` is a team id: the acting user must be a member of that team."""

    def __init__(self, identity_provider: IdentityProvider, holder: Optional[ExecutionContextHolder]) -> None:
        self._provider = identity_provider
        self._holder = holder

    def authorize(self, scope_id: str) -> None:
        user = acting_user(self._holder)
        try:
            member = self._provider.is_member(user, scope_id)
        except Exception:
            logger.warning("memory.access.provider_error", extra={"scope_id": scope_id}, exc_info=True)
            raise ScopeAccessDenied(f"{ACCESS_REFUSED_PREFIX}: team membership could not be verified") from None
        if member is not True:
            raise ScopeAccessDenied(f"{ACCESS_REFUSED_PREFIX}: the acting user is not a member of this scope")


class OwnerScopeAccessChecker:
    """The scope is owned by the acting user: ``scope_id`` must equal the acting user id."""

    def __init__(self, holder: Optional[ExecutionContextHolder]) -> None:
        self._holder = holder

    def authorize(self, scope_id: str) -> None:
        if acting_user(self._holder) != scope_id:
            raise ScopeAccessDenied(f"{ACCESS_REFUSED_PREFIX}: this scope is owned by another user")


def build_access_checker(
    mode: AccessMode,
    identity_provider: Optional[IdentityProvider],
    holder: Optional[ExecutionContextHolder],
) -> Optional[Any]:
    """Return the checker for *mode*, or ``None`` for mode ``none``.

    Raises ``ValueError`` when the mode needs a dependency that is not available,
    so a misconfigured tool fails at build time instead of running unprotected.
    """
    if mode == AccessMode.NONE:
        return None
    if holder is None:
        raise ValueError(f"access mode '{mode.value}' needs an execution context")
    if mode == AccessMode.TEAM:
        if identity_provider is None:
            raise ValueError("access mode 'team' needs an identity provider")
        return TeamScopeAccessChecker(identity_provider, holder)
    if mode == AccessMode.OWNER:
        return OwnerScopeAccessChecker(holder)
    raise ValueError(f"unknown access mode: {mode}")
