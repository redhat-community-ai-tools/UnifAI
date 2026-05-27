"""
Flask decorators for access control.

Provides pluggable decorator factories consumed by any Flask-based service:

- ``require_team_session``: validates a Redis-backed server session and resolves
  a user-or-team Identity.  The single auth decorator for services that need
  team-aware identity context (e.g. MAS).
- ``require_admin_access``: gates endpoints to admin users via caller-supplied
  callbacks.
"""
from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request

from global_utils.identity import resolve_identity
from global_utils.redis import get_identity_session

G_IDENTITY_SESSION = "identity_session"
G_IDENTITY_USERNAME = "identity_username"
G_IDENTITY = "identity"


def require_team_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None],
    check_team_membership: Callable[[str, str], bool] | None = None,
    resolve_display_name: Callable[[str, str], str] | None = None,
) -> Callable:
    """Decorator factory: validate Redis session + resolve user-or-team Identity.

    Combines session validation (via Redis) with identity resolution into a
    single decorator pass.

    Each app supplies:
      - ``get_redis_store()`` → store with ``hget``
      - ``get_session_id()``  → session id from the current request
        (no default — caller must wire explicitly)
      - ``check_team_membership(username, team_id) → bool`` (optional)
      - ``resolve_display_name(username, team_id) → str`` (optional)
        When provided, the decorator resolves team display names server-side
        instead of relying on the client to send ``displayName``.

    Identity resolution:
      - If ``teamId`` is present in the request (query, body, or kwargs),
        the identity is resolved as a team.
      - Otherwise, the identity is the authenticated user from the Redis
        session (no client-supplied ``userId`` needed).

    On success, sets on ``flask.g``:
      - ``g.identity_session``  → :class:`UserSessionData`
      - ``g.identity_username`` → ``str`` (the human username from Redis)
      - ``g.identity``          → :class:`Identity`

    The decorated function receives one extra keyword argument:
      - ``identity`` → the resolved :class:`Identity`

    Endpoints that need the raw human username (e.g. collaboration locks,
    presence, admin gates) should read ``g.identity_username``.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                # ── 1. Session validation ─────────────────────────────
                sid = get_session_id()
                data = get_identity_session(get_redis_store(), sid)
                if data is None or not data.has_auth_credentials():
                    return (
                        jsonify({
                            "error": "Not authenticated",
                            "error_type": "AUTHENTICATION_REQUIRED",
                        }),
                        401,
                    )

                username = str(data.username).strip()
                setattr(g, G_IDENTITY_SESSION, data)
                setattr(g, G_IDENTITY_USERNAME, username)

                # ── 2. Resolve identity (session user + optional team) ─
                body = request.get_json(silent=True) or {}

                team_id = str(
                    request.args.get("teamId")
                    or body.get("teamId")
                    or kwargs.get("teamId")
                    or kwargs.get("team_id")
                    or ""
                ).strip()

                if team_id:
                    if check_team_membership is not None and not check_team_membership(username, team_id):
                        return (
                            jsonify({
                                "error": "Access denied: you are not a member of this team",
                                "error_type": "TEAM_ACCESS_DENIED",
                            }),
                            403,
                        )
                    display_name = ""
                    if resolve_display_name is not None:
                        display_name = resolve_display_name(username, team_id)
                    identity = resolve_identity(team_id, "team", display_name)
                else:
                    identity = resolve_identity(username, "user")

                # ── 3. Set context ────────────────────────────────────
                setattr(g, G_IDENTITY, identity)
                kwargs["identity"] = identity

                return f(*args, **kwargs)
            except ValueError as e:
                return (
                    jsonify({"error": str(e)}),
                    400,
                )
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
