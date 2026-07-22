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
"""
from flask import current_app, g, jsonify

from inbound.flask.decorators import G_IDENTITY_USERNAME


def collaboration_service_or_error():
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


def holder_to_json(holder):
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }


def reject_if_locked_by_other(resource_id: str):
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
    if holder.user_id == username:
        return None
    return jsonify({
        "error": f"Resource is currently locked for editing by "
                 f"{holder.display_name or holder.user_id}.",
        "lockedBy": holder_to_json(holder),
    }), 409
