"""Object-level access checks for session and blueprint-use routes.

The guards read the signed-in username resolved by the identity decorators
(``g.identity_username``), so they must sit below one of them. Denial is
uniform: an unknown object and an object the caller may not use produce the
same response.
"""
import logging
from functools import wraps
from typing import Any, Callable, Optional

from flask import current_app, g, jsonify

from inbound.flask.decorators import G_IDENTITY_USERNAME, is_admin_user
from mas.collaboration.access import check_session_access
from mas.core.identity import IdentityType
from mas.session.domain.session_record import SessionRecord

logger = logging.getLogger(__name__)


def session_not_found():
    return jsonify({"error": "Session not found"}), 404


def caller_username() -> str:
    return str(getattr(g, G_IDENTITY_USERNAME, "") or "").strip()


def authorize_session(session_id: str) -> tuple[Optional[SessionRecord], Optional[tuple]]:
    """Return ``(record, None)`` when the caller may use the session,
    else ``(None, uniform_not_found_response)``."""
    username = caller_username()
    if not username or not session_id:
        return None, session_not_found()
    container = current_app.container
    try:
        record = check_session_access(
            container.session_repo, container.identity_provider, username, session_id,
        )
    except (KeyError, PermissionError):
        return None, session_not_found()
    return record, None


def require_session_access(f: Callable[..., Any]) -> Callable[..., Any]:
    """Reject the request unless the caller owns the session or belongs to its team.

    Place below ``@from_body`` / ``@from_query`` so ``session_id`` is injected.
    """
    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        _, err = authorize_session(str(kwargs.get("session_id") or ""))
        if err is not None:
            return err
        return f(*args, **kwargs)
    return wrapped


def can_use_blueprint(blueprint_id: str, username: str) -> bool:
    """True when the user owns the blueprint, belongs to the owning team,
    is an admin, or the blueprint is published with ``usageScope=public``."""
    container = current_app.container
    try:
        doc = container.blueprint_service.get_blueprint_draft_doc(blueprint_id)
    except KeyError:
        return False
    if (doc.metadata or {}).get("usageScope") == "public":
        return True
    if doc.identity.type == IdentityType.TEAM:
        if container.identity_provider.is_member(username, doc.identity.id):
            return True
    elif username.casefold() == doc.identity.id.casefold():
        return True
    return is_admin_user(username)
