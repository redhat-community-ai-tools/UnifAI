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

from global_utils.identity import resolve_identity
from global_utils.redis import get_identity_session, get_identity_username

G_IDENTITY_SESSION = "identity_session"
G_IDENTITY_USERNAME = "identity_username"
G_IDENTITY = "identity"


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


def require_team_session(
    get_redis_store: Callable[[], Any],
    get_session_id: Callable[[], str | None],
    check_team_membership: Callable[[str, str], bool] | None = None,
    resolve_display_name: Callable[[str, str], str] | None = None,
) -> Callable:
    """Decorator factory: validate Redis session + resolve user-or-team Identity.

    Combines session validation (via Redis) with identity resolution into a
    single decorator pass.  Intended as the successor to
    :func:`require_identity_session` for endpoints that also need team-aware
    identity context.

    Each app supplies:
      - ``get_redis_store()`` → store with ``hget``
      - ``get_session_id()``  → session id from the current request
        (no default — caller must wire explicitly)
      - ``check_team_membership(username, team_id) → bool`` (optional)
      - ``resolve_display_name(username, team_id) → str`` (optional)
        When provided, the decorator resolves team display names server-side
        instead of relying on the client to send ``displayName``.

    Identity resolution:
      - **New contract:** if ``teamId`` is present in the request (query or
        body), the workspace is treated as a team; otherwise personal.  The
        authenticated user is always resolved from the session — no need for
        the client to send ``userId``.
      - **Legacy contract (backward-compat):** ``userId`` + ``identityType``
        still works for callers that haven't migrated (e.g. CLI).

    On success, sets on ``flask.g``:
      - ``g.identity_session``  → :class:`UserSessionData`
      - ``g.identity_username`` → ``str``
      - ``g.identity``          → :class:`Identity`

    The decorated function receives two extra keyword arguments:
      - ``identity``           → the resolved :class:`Identity`
      - ``authenticated_user`` → the human username from the Redis session
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

                # ── 2. Parse identity params ──────────────────────────
                body = request.get_json(silent=True) or {}

                # New contract: teamId signals team workspace
                team_id = str(
                    request.args.get("teamId")
                    or body.get("teamId")
                    or kwargs.get("teamId")
                    or kwargs.get("team_id")
                    or ""
                ).strip()

                if team_id:
                    # ── New path: teamId present → team workspace ─────
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
                    # ── Legacy compat: userId/identityType ────────────
                    user_id = str(
                        request.args.get("userId")
                        or body.get("userId")
                        or kwargs.get("userId")
                        or kwargs.get("user_id")
                        or ""
                    ).strip()
                    identity_type = str(
                        request.args.get("identityType")
                        or body.get("identityType")
                        or kwargs.get("identityType")
                        or kwargs.get("identity_type")
                        or "user"
                    ).strip().lower() or "user"
                    display_name = str(
                        request.args.get("displayName")
                        or body.get("displayName")
                        or kwargs.get("displayName")
                        or kwargs.get("display_name")
                        or ""
                    )

                    if not user_id:
                        user_id = username
                        identity_type = "user"

                    # ── Authorize ─────────────────────────────────────
                    if identity_type == "team":
                        if check_team_membership is not None and not check_team_membership(username, user_id):
                            return (
                                jsonify({
                                    "error": "Access denied: you are not a member of this team",
                                    "error_type": "TEAM_ACCESS_DENIED",
                                }),
                                403,
                            )
                        if not display_name and resolve_display_name is not None:
                            display_name = resolve_display_name(username, user_id)
                    elif user_id.casefold() != username.casefold():
                        return (
                            jsonify({
                                "error": "Access denied: userId does not match authenticated user",
                                "error_type": "USER_ACCESS_DENIED",
                            }),
                            403,
                        )

                    identity = resolve_identity(user_id, identity_type, display_name)

                # ── 3. Set context ────────────────────────────────────
                setattr(g, G_IDENTITY, identity)
                kwargs["identity"] = identity
                kwargs["authenticated_user"] = username

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
