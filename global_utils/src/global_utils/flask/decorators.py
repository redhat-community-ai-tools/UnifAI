"""
Flask decorators for access control.

Pluggable so each app can supply its own way to get the current user
and to check admin status (e.g. from config, DB, or admin config service).

Also provides identity-session decorators that validate callers against
a Redis-backed server session written by the Identity service after
Keycloak login.  These are generic (no MAS/domain concepts) and can be
consumed by any Flask-based service.
"""
from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request, session

from global_utils.redis import get_identity_session, get_identity_username

G_IDENTITY_SESSION = "identity_session"
G_IDENTITY_USERNAME = "identity_username"


def require_identity_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
) -> Callable:
    """
    Decorator factory: require a valid identity server session in Redis.

    A session is "valid" when :meth:`UserSessionData.has_auth_credentials`
    is true (username + access_token present — same bar as the identity
    service ``is_authenticated``).

    Each app supplies:
      - ``get_redis_store()`` -> store with ``hget``
        (e.g. :class:`global_utils.redis.RedisKVStore`)
      - ``get_session_id()`` -> str | None
        (optional; default: ``session.get("session_id")``)

    On success: sets ``g.identity_session`` to a :class:`UserSessionData`.
    On failure: 401 with JSON; unexpected errors: 500 with ``error_type``.
    """
    get_sid = get_session_id or (lambda: session.get("session_id"))

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                data = get_identity_session(get_redis_store(), get_sid())
                if data is None or not data.has_auth_credentials():
                    return (
                        jsonify({
                            "error": "Not authenticated",
                            "error_type": "AUTHENTICATION_REQUIRED",
                        }),
                        401,
                    )
                setattr(g, G_IDENTITY_SESSION, data)
                return f(*args, **kwargs)
            except Exception as e:
                return (
                    jsonify({
                        "error": f"Access control error: {e!s}",
                        "error_type": "ACCESS_CONTROL_ERROR",
                    }),
                    500,
                )
        return wrapped
    return decorator


def require_identity_username(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
) -> Callable:
    """
    Decorator factory: require a non-empty ``username`` from the Redis server session.

    Weaker than :func:`require_identity_session` (does not check access_token).
    Prefer the full session decorator for API paths that need the same bar as
    the identity service.

    On success: sets ``g.identity_username`` (see :data:`G_IDENTITY_USERNAME`).
    """
    get_sid = get_session_id or (lambda: session.get("session_id"))

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                username = get_identity_username(get_redis_store(), get_sid())
                if not username:
                    return (
                        jsonify({
                            "error": "Not authenticated",
                            "error_type": "AUTHENTICATION_REQUIRED",
                        }),
                        401,
                    )
                setattr(g, G_IDENTITY_USERNAME, username)
                return f(*args, **kwargs)
            except Exception as e:
                return (
                    jsonify({
                        "error": f"Access control error: {e!s}",
                        "error_type": "ACCESS_CONTROL_ERROR",
                    }),
                    500,
                )
        return wrapped
    return decorator


def require_admin_access(get_current_user, is_admin):
    """
    Decorator factory: require admin access for an endpoint.

    Each app supplies:
      - get_current_user(request) -> str | None
        Return the current user identifier (e.g. username or user_id), or None if unknown.
      - is_admin(user_id: str) -> bool
        Return True if the user is an admin. Can use current_app inside.

    Returns:
        401 Unauthorized if no current user.
        403 Forbidden if the user is not an admin.
        500 on unexpected errors (with error_type ACCESS_CONTROL_ERROR).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                user_id = get_current_user(request)
                if not user_id:
                    return jsonify({
                        "error": "Access denied: user identification is required",
                        "error_type": "AUTHENTICATION_REQUIRED",
                    }), 401
                if not is_admin(user_id):
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
    return decorator
