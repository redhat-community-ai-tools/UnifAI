"""
Inbound identity adapter — Flask middleware for session validation and authorization.

This module is the MAS entry point for all identity concerns at the HTTP layer:

- ``with_require_team_session``: validates the Redis-backed server session via
  ``X-Session-Id`` and resolves a user-or-team Identity.
- ``require_admin_access``: gates endpoints to configured admin users.
- ``build_team_session_decorator``: one-time startup wiring that connects the
  generic ``global_utils`` session decorator to MAS's container (Redis store,
  IdentityProvider port).

The heavy lifting (Redis reads, identity resolution) is in
``global_utils.flask.decorators``; this module supplies MAS-specific wiring and
the thin runtime proxy that endpoints import.
"""
import logging
from functools import wraps

from flask import Flask, current_app, g, jsonify, request

from mas.core.identity import Identity as DomainIdentity
from mas.core.identity.ports import IdentityProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Admin access gate
# ──────────────────────────────────────────────────────────────────────────────

def require_admin_access(f):
    """Gate an endpoint to users listed in ``admin_allowed_users``.

    Reads the human username from ``g.identity_username`` (set by
    ``with_require_team_session``).  Must be stacked below it.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            admin_allowed_users = current_app.config.get("admin_allowed_users", [])

            if not admin_allowed_users:
                return jsonify({
                    "error": "Access denied: Analytics is not enabled",
                    "error_type": "FEATURE_DISABLED",
                }), 403

            user_id = getattr(g, "identity_username", None)

            if not user_id:
                return jsonify({
                    "error": "Access denied: user identification is required",
                    "error_type": "AUTHENTICATION_REQUIRED",
                }), 401

            if user_id not in admin_allowed_users:
                return jsonify({
                    "error": "Access denied: insufficient permissions",
                    "error_type": "ACCESS_DENIED",
                }), 403

            return f(*args, **kwargs)

        except Exception as e:
            return jsonify({
                "error": f"Access control error: {str(e)}",
                "error_type": "ACCESS_CONTROL_ERROR",
            }), 500

    return decorated_function


# ──────────────────────────────────────────────────────────────────────────────
# Redis session-validated decorator
# ──────────────────────────────────────────────────────────────────────────────

_TEAM_SESSION_EXT = "team_session_decorator"


def build_team_session_decorator(app: Flask, container: object) -> bool:
    """Wire the team-session decorator once at app startup.

    Reads ``container.redis_store`` and ``container.identity_provider``.
    Stores the resulting decorator in ``app.extensions`` so
    :func:`with_require_team_session` can retrieve it without per-request
    overhead.

    Returns ``True`` if the decorator was built, ``False`` if Redis is
    unavailable (endpoints using the decorator will return 503).
    """
    redis_store = getattr(container, "redis_store", None)
    if redis_store is None:
        logger.warning(
            "Redis store not available — with_require_team_session will return 503"
        )
        return False

    provider: IdentityProvider = container.identity_provider

    from global_utils.flask.decorators import require_team_session

    decorator = require_team_session(
        get_redis_store=lambda: redis_store,
        get_session_id=lambda: request.headers.get("X-Session-Id", "").strip(),
        check_team_membership=(
            provider.is_member if provider.requires_authentication else None
        ),
        resolve_display_name=(
            provider.resolve_team_display_name if provider.requires_authentication else None
        ),
    )
    app.extensions[_TEAM_SESSION_EXT] = decorator
    logger.info("Team-session decorator built (Redis session validation enabled)")
    return True


def with_require_team_session(f):
    """Validate caller via Redis session + resolve Identity.

    Reads the ``X-Session-Id`` header and validates the server session in
    Redis.  On success, injects ``identity`` (:class:`Identity`) as a
    keyword argument and sets ``g.identity_username`` to the human
    username from the session.

    Requires :func:`build_team_session_decorator` to have been called at
    startup.  If Redis was not available at startup, returns 503.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        decorator = current_app.extensions.get(_TEAM_SESSION_EXT)
        if decorator is None:
            return jsonify({
                "error": "Session validation not available",
                "error_type": "SERVICE_UNAVAILABLE",
            }), 503

        @wraps(f)
        def _convert_identity(*inner_args, **inner_kwargs):
            gu_identity = inner_kwargs.get("identity")
            if gu_identity is not None and not isinstance(gu_identity, DomainIdentity):
                inner_kwargs["identity"] = DomainIdentity.model_validate(
                    gu_identity.model_dump()
                )
            return f(*inner_args, **inner_kwargs)

        return decorator(_convert_identity)(*args, **kwargs)
    return decorated
