"""
Flask decorators for identity resolution and authorization.

``with_require_team_session`` is the single auth decorator for all MAS
endpoints.  It validates a Redis-backed server session (via ``X-Session-Id``
header) and resolves a user-or-team Identity — replacing the legacy
header-trust decorators.
"""
import logging
from functools import wraps

from flask import Flask, current_app, jsonify, request

from mas.core.identity.ports import IdentityProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Admin access gate
# ──────────────────────────────────────────────────────────────────────────────

def require_admin_access(f):
    """Gate an endpoint to users listed in ``admin_allowed_users``.

    Prefers ``authenticated_user`` injected by ``with_require_team_session``
    (server-validated).  Falls back to ``userId`` / ``user_id`` from kwargs or
    query params for backward compatibility.
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

            user_id = (
                kwargs.get("authenticated_user")
                or kwargs.get("user_id")
                or kwargs.get("userId")
                or request.args.get("user_id")
                or request.args.get("userId")
            )

            if not user_id:
                return jsonify({
                    "error": "Access denied: user_id is required",
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
    Redis.  On success, injects into kwargs:

      - ``identity`` — resolved :class:`Identity` (user or team)
      - ``authenticated_user`` — the validated username from the Redis session

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
        return decorator(f)(*args, **kwargs)
    return decorated
