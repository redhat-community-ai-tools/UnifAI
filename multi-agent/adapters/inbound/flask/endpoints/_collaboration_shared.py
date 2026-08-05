"""Shared collaboration-service helpers for Flask endpoint modules.

``collaboration_service_or_error`` and ``holder_to_json`` are generic
helpers used by every collaboration surface (admin edit locks here, plus
team edit locks and presence in ``collaboration/locks.py`` and
``collaboration/presence.py``) — they were previously copy-pasted
identically into each of those three modules.

``reject_if_locked_by_other`` is specific to the *admin* edit lock: it's
shared by ``builtins.py`` (admin-only built-in routes) and ``resources.py``
(the generic resource CRUD routes, which admins also use to mutate
built-in resources via ``guard_write_access``) so both enforce the same
cooperative lock instead of only the former.

``guard_write_access_with_lock`` combines the ownership/admin check with
the cooperative lock check for the generic resource CRUD routes —
``resources.py``'s ``update_resource`` and ``delete_resource`` both need
"authorize the mutation, then reject if a built-in is locked by another
admin" and previously duplicated that combination inline.
"""
from typing import Any, Optional

from flask import Response, current_app, g, jsonify

from inbound.flask.decorators import G_IDENTITY_USERNAME
from mas.collaboration.models import TeamEditLockHolder
from mas.collaboration.service import CollaborationService
from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceOwnership
from mas.resources.models import Resource
from mas.resources.service import ResourcesService


def collaboration_service_or_error() -> tuple[
    Optional[CollaborationService], Optional[tuple[Response, int]]
]:
    """Return ``(service, None)``, or ``(None, (response, 501))`` if the
    collaboration service (Redis) isn't configured.

    Callers should short-circuit and return the error tuple as-is when it
    isn't ``None``, e.g.::

        svc, err = collaboration_service_or_error()
        if err:
            return err
    """
    svc = current_app.container.collaboration_service
    if svc is None:
        return None, (jsonify(
            {"error": "Collaboration service not available - Redis is not configured"}
        ), 501)
    return svc, None


def holder_to_json(holder: Optional[TeamEditLockHolder]) -> Optional[dict[str, Any]]:
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }


def reject_if_locked_by_other(resource_id: str) -> Optional[tuple[Response, int]]:
    """Enforce the admin edit lock on mutating built-in endpoints.

    The lock is acquired cooperatively by the UI when an admin opens the
    edit form. This guards against a second request (a stale tab, a
    direct API call, a client that skipped the acquire step) mutating the
    same resource anyway — without it the lock is advisory only.
    Returns a ``(response, 409)`` tuple to short-circuit the caller when
    another admin currently holds the lock, or ``None`` to proceed.
    Requests are never blocked when collaboration/Redis isn't configured,
    matching the acquire/release endpoints' 501 fallback behavior.
    """
    collab = current_app.container.collaboration_service
    if collab is None:
        return None
    holder = collab.get_admin_edit_lock(resource_id)
    if holder is None:
        return None
    username = getattr(g, G_IDENTITY_USERNAME, "")
    if holder.user_id.casefold() == username.casefold():
        return None
    return jsonify({
        "error": f"Resource is currently locked for editing by "
                 f"{holder.display_name or holder.user_id}.",
        "lockedBy": holder_to_json(holder),
    }), 409


def guard_write_access_with_lock(
    resources_service: ResourcesService,
    resource_id: str,
    *,
    caller: CallerScope,
) -> tuple[Optional[Resource], Optional[tuple[Response, int]]]:
    """Authorize a mutation and enforce the admin edit lock in one call.

    Runs ``ResourcesService.guard_write_access`` (ownership/admin checks —
    raises on failure, same as calling it directly) and, for built-in
    resources, also rejects the request with ``(response, 409)`` if
    another admin currently holds the edit lock. Returns
    ``(resource, None)`` to proceed.
    """
    resource = resources_service.guard_write_access(resource_id, caller)
    if resource.ownership == ResourceOwnership.BUILTIN:
        lock_error = reject_if_locked_by_other(resource_id)
        if lock_error:
            return None, lock_error
    return resource, None
