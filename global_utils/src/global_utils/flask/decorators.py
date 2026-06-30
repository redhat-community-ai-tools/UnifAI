"""
Flask decorators for access control.

Pluggable so each app can supply its own way to get the current user
and to check admin status (e.g. from config, DB, or admin config service).

Also provides identity-session decorators that validate callers against
a Redis-backed server session written by the Identity service after
Keycloak login.  These are generic (no MAS/domain concepts) and can be
consumed by any Flask-based service.
"""
import logging
from functools import wraps
from typing import Any, Callable, Optional, Tuple

from flask import g, jsonify, request, session
from werkzeug.exceptions import HTTPException

from global_utils.redis import get_identity_session, get_identity_username
from global_utils.redis.session_model import UserSessionData

logger = logging.getLogger(__name__)

G_IDENTITY_SESSION = "identity_session"
G_IDENTITY_USERNAME = "identity_username"
G_USER_ID = "user_id"
G_TEAM_ID = "team_id"

_AUTH_REQUIRED = ("Not authenticated", "AUTHENTICATION_REQUIRED", 401)
_SESSION_EXPIRED = ("Session expired", "SESSION_EXPIRED", 401)
_TEAM_DENIED = ("Access denied: not a member of this team", "TEAM_ACCESS_DENIED", 403)


def validate_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None],
    get_fallback_user: Callable[[], str | None] | None = None,
) -> Tuple[Optional[UserSessionData], Optional[tuple]]:
    """Validate the Redis-backed server session.

    Returns ``(data, None)`` on success or ``(None, error_tuple)`` on failure.
    The error tuple is ``(message, error_type, status_code)``.

    When *get_fallback_user* is provided and session validation fails (missing
    or invalid session), the callback is tried before returning 401.  If it
    returns a non-empty username, a minimal :class:`UserSessionData` is
    synthesised.  This supports legacy CI/CD scripts that send
    ``X-Authenticated-User`` until API-token auth is available.
    """
    sid = get_session_id()
    if not sid:
        return _try_fallback_or_fail(get_fallback_user, _AUTH_REQUIRED)
    data = get_identity_session(get_redis_store(), sid)
    if data is None or not data.has_auth_credentials():
        return _try_fallback_or_fail(get_fallback_user, _AUTH_REQUIRED)
    if data.is_session_expired():
        return None, _SESSION_EXPIRED
    return data, None


def _try_fallback_or_fail(
    get_fallback_user: Callable[[], str | None] | None,
    error: tuple,
) -> Tuple[Optional[UserSessionData], Optional[tuple]]:
    """Try the fallback callback; return its result or the original error."""
    if get_fallback_user is not None:
        username = get_fallback_user()
        if username:
            return UserSessionData(username=username), None
    return None, error


def require_identity_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
    get_fallback_user: Callable[[], str | None] | None = None,
) -> Callable:
    """
    Decorator factory: require a valid identity server session in Redis.

    A session is "valid" when :meth:`UserSessionData.has_auth_credentials`
    is true (username + access_token present — same bar as the identity
    service ``is_authenticated``) and the session has not expired.

    Each app supplies:
      - ``get_redis_store()`` -> store with ``hget``
        (e.g. :class:`global_utils.redis.RedisKVStore`)
      - ``get_session_id()`` -> str | None
        (optional; default: ``session.get("session_id")``)
      - ``get_fallback_user()`` -> str | None
        (optional; called when session validation fails, returns a
        fallback username or ``None``)

    On success: sets ``g.identity_session`` to a :class:`UserSessionData`.
    On failure: 401 with JSON; unexpected errors: 500 with ``error_type``.
    """
    get_sid = get_session_id or (lambda: session.get("session_id"))

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                data, err = validate_session(get_redis_store, get_sid, get_fallback_user)
                if err:
                    msg, err_type, status = err
                    return jsonify({"error": msg, "error_type": err_type}), status
                setattr(g, G_IDENTITY_SESSION, data)
                return f(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.exception("Session validation failed unexpectedly")
                return (
                    jsonify({
                        "error": "Internal server error",
                        "error_type": "ACCESS_CONTROL_ERROR",
                    }),
                    500,
                )
        return wrapped
    return decorator


def require_team_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None] | None = None,
    get_team_id: Callable[[], str | None] | None = None,
    team_membership_checker: Callable[[str, str], bool] | None = None,
    get_fallback_user: Callable[[], str | None] | None = None,
) -> Callable:
    """
    Decorator factory: require a valid identity session + optional team authorization.

    Validates the caller's Redis-backed server session (same as
    :func:`require_identity_session`), then optionally checks team membership
    via the supplied ``team_membership_checker`` callback.

    Each app supplies:
      - ``get_redis_store()`` -> store with ``hget``
      - ``get_session_id()`` -> str | None  (default: ``session.get("session_id")``)
      - ``get_team_id()``    -> str | None  (default: ``None`` — no team check)
      - ``team_membership_checker(username, team_id) -> bool``
        (e.g. ``IdentityClient.is_member``)
      - ``get_fallback_user()`` -> str | None
        (optional; called when session validation fails, returns a
        fallback username or ``None``)

    On success: sets ``g.identity_session``, ``g.user_id``, and optionally ``g.team_id``.
    On failure: 401 / 403 / 500 with JSON error payload.
    """
    get_sid = get_session_id or (lambda: session.get("session_id"))

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                data, err = validate_session(get_redis_store, get_sid, get_fallback_user)
                if err:
                    msg, err_type, status = err
                    return jsonify({"error": msg, "error_type": err_type}), status

                setattr(g, G_IDENTITY_SESSION, data)
                setattr(g, G_USER_ID, data.username)

                if get_team_id is not None:
                    team_id = get_team_id()
                    if team_id and team_membership_checker is not None:
                        if not team_membership_checker(data.username, team_id):
                            msg, err_type, status = _TEAM_DENIED
                            return jsonify({"error": msg, "error_type": err_type}), status
                        setattr(g, G_TEAM_ID, team_id)

                return f(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.exception("Team session validation failed unexpectedly")
                return (
                    jsonify({
                        "error": "Internal server error",
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
                logger.exception("Username validation failed unexpectedly")
                return (
                    jsonify({
                        "error": "Internal server error",
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
                logger.exception("Admin access check failed unexpectedly")
                return jsonify({
                    "error": "Internal server error",
                    "error_type": "ACCESS_CONTROL_ERROR",
                }), 500
        return decorated_function
    return decorator
