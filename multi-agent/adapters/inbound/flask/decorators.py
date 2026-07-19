"""
Flask decorator for identity resolution and authorization.

Validates the caller via a Redis-backed server session (set by the Identity
service at login) and resolves the workspace identity:

- **User identity:** Derived from the session cookie. No client-supplied
  ``userId`` is needed.
- **Team identity:** The client sends ``teamId`` (query param, JSON body, or
  URL kwarg). Its presence triggers team mode; the decorator validates
  membership before proceeding.

Internal services (e.g. the backend relaying Slack commands) authenticate
via the ``X-Authenticated-User`` header.

Backward compatibility: The decorator still accepts legacy ``userId`` +
``identityType`` params from older UI/CLI clients. These are mapped to the
new model transparently and will be removed in a follow-up PR.
"""
import logging
from functools import wraps
from typing import Any, Callable

from flask import current_app, g, jsonify, request, session

from global_utils.flask.decorators import validate_session, G_IDENTITY_SESSION
from mas.core.identity import resolve_identity
from mas.core.identity.ports import IdentityProvider

logger = logging.getLogger(__name__)

G_IDENTITY = "identity"
G_IDENTITY_USERNAME = "identity_username"


# ──────────────────────────────────────────────────────────────────────────────
# Provider access
# ──────────────────────────────────────────────────────────────────────────────

def _identity_provider() -> IdentityProvider:
    return current_app.container.identity_provider


def _get_redis_store():
    return current_app.container.redis_kv_store


# ──────────────────────────────────────────────────────────────────────────────
# Session callbacks
# ──────────────────────────────────────────────────────────────────────────────

_AUTH_HEADER = "X-Authenticated-User"


def _get_fallback_user() -> str | None:
    """Fallback authentication for non-browser callers.

    Reads the ``X-Authenticated-User`` header set by trusted internal
    services (e.g. the backend relaying Slack commands).  The value is
    the Slack *username* (e.g. ``sfiresht``), which matches the identity
    stored in MongoDB for session ownership.
    """
    user = request.headers.get(_AUTH_HEADER, "").strip()
    if user:
        logger.debug("Authenticated via %s header: %s", _AUTH_HEADER, user)
        return user

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Team ID extraction
# ──────────────────────────────────────────────────────────────────────────────

def _extract_team_id(kwargs: dict) -> str:
    """Extract team_id from the request.

    Priority:
      1. ``teamId`` query param / JSON body / URL kwarg (new contract)
      2. Legacy: ``identityType=team`` + ``userId`` as the team id
      3. Empty string → user mode
    """
    body = request.get_json(silent=True) or {}

    # New contract: explicit teamId
    team_id = str(
        request.args.get("teamId")
        or body.get("teamId")
        or kwargs.get("teamId")
        or kwargs.get("team_id")
        or ""
    ).strip()

    if team_id:
        return team_id

    # Backward compat: legacy identityType + userId
    identity_type = (
        request.args.get("identityType")
        or body.get("identityType")
        or kwargs.get("identityType")
        or kwargs.get("identity_type")
        or "user"
    ).strip().lower()

    if identity_type == "team":
        legacy_id = str(
            request.args.get("userId")
            or body.get("userId")
            or kwargs.get("userId")
            or kwargs.get("user_id")
            or ""
        ).strip()
        return legacy_id

    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Unified decorator
# ──────────────────────────────────────────────────────────────────────────────

def require_session_identity(f: Callable) -> Callable:
    """Validate session and resolve workspace identity.

    This is the single auth decorator for all MAS endpoints. It:

    1. Validates the Redis-backed server session (cookie or fallback header).
    2. Resolves the workspace identity:
       - If ``teamId`` is present → team identity (membership validated).
       - Otherwise → user identity derived from the session username.
    3. Injects ``identity`` keyword argument into the endpoint.
    4. Sets ``g.identity_session``, ``g.identity_username``, ``g.identity``.

    Endpoints that need the raw human username (e.g. collaboration locks,
    presence) should read ``g.identity_username``.
    """
    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            # 1. Session validation
            data, err = validate_session(
                _get_redis_store,
                lambda: session.get("session_id"),
                _get_fallback_user,
            )
            if err:
                msg, err_type, status = err
                return jsonify({"error": msg, "error_type": err_type}), status

            username = str(data.username).strip()
            setattr(g, G_IDENTITY_SESSION, data)
            setattr(g, G_IDENTITY_USERNAME, username)

            # 2. Resolve identity
            team_id = _extract_team_id(kwargs)

            if team_id:
                if not _identity_provider().is_member(username, team_id):
                    return jsonify({
                        "error": "Access denied: you are not a member of this team",
                        "error_type": "TEAM_ACCESS_DENIED",
                    }), 403
                display_name = _identity_provider().resolve_team_display_name(username, team_id)
                identity = resolve_identity(team_id, "team", display_name)
            else:
                identity = resolve_identity(username, "user")

            # 3. Set context and inject
            setattr(g, G_IDENTITY, identity)
            kwargs["identity"] = identity
            return f(*args, **kwargs)

        except ValueError as e:
            return jsonify({"error": str(e), "error_type": "INVALID_IDENTITY"}), 400
        except Exception:
            logger.exception("Identity resolution failed unexpectedly")
            return jsonify({
                "error": "Internal server error",
                "error_type": "ACCESS_CONTROL_ERROR",
            }), 500

    return wrapped


# ──────────────────────────────────────────────────────────────────────────────
# Legacy aliases (backward compat for endpoints not yet migrated)
# ──────────────────────────────────────────────────────────────────────────────

def with_authenticated_user(f: Callable) -> Callable:
    """Legacy wrapper: validates session, injects ``authenticated_user`` kwarg.

    Delegates to :func:`require_session_identity`, then bridges ``identity``
    into the ``authenticated_user`` string that old endpoints expect.
    """
    @wraps(f)
    def bridge(*args: Any, **kwargs: Any) -> Any:
        identity = kwargs.pop("identity", None)
        kwargs["authenticated_user"] = getattr(g, G_IDENTITY_USERNAME, "")
        return f(*args, **kwargs)
    return require_session_identity(bridge)


def with_require_identity_authorization(f: Callable) -> Callable:
    """Legacy wrapper: validates session + resolves identity.

    Same as :func:`require_session_identity` — kept as an alias so existing
    endpoint decorators don't break. The ``identity`` kwarg is passed through.
    """
    return require_session_identity(f)


def with_identity(f: Callable) -> Callable:
    """Legacy wrapper: resolves identity without full session validation.

    Now equivalent to :func:`require_session_identity` (session is always
    validated). Kept for backward compat.
    """
    return require_session_identity(f)


# ──────────────────────────────────────────────────────────────────────────────
# Admin access (unchanged)
# ──────────────────────────────────────────────────────────────────────────────

def is_admin_user(username: str) -> bool:
    """Check admin status via the container's admin config reader,
    falling back to the static ``admin_allowed_users`` Flask config.

    Public accessor other endpoint modules should use (e.g. to build
    ``is_admin`` flags for service calls) instead of reaching into this
    module's private implementation detail.

    Mirrors the backend pattern where this delegates to
    ``current_app.container.admin_config_service.is_admin()``.
    """
    container = getattr(current_app, "container", None)
    reader = getattr(container, "admin_config_reader", None) if container else None
    if reader and reader.is_admin(username):
        return True
    admin_allowed_users = current_app.config.get("admin_allowed_users", [])
    return username.lower() in [u.lower() for u in admin_allowed_users]


# Backward-compat alias for any remaining internal call sites within this module.
_is_admin = is_admin_user


def require_admin_access(f):
    """Gate an endpoint to admin users.

    Reads the authenticated username from the session (via
    :func:`require_session_identity`) and checks admin status through
    ``current_app.container.admin_config_reader`` (centralized admin
    config managed via the admin panel).  Falls back to the static
    ``admin_allowed_users`` Flask config.

    Does NOT inject ``identity`` into the wrapped function's kwargs.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            kwargs.pop("identity", None)

            username = getattr(g, G_IDENTITY_USERNAME, "")
            if not username:
                return jsonify({
                    "error": "Access denied: user identification is required",
                    "error_type": "AUTHENTICATION_REQUIRED",
                }), 401

            if not _is_admin(username):
                return jsonify({
                    "error": "Access denied: insufficient permissions",
                    "error_type": "ACCESS_DENIED",
                }), 403

            return f(*args, **kwargs)
        except Exception:
            logger.exception("Admin access check failed unexpectedly")
            return jsonify({
                "error": "Internal server error",
                "error_type": "ACCESS_CONTROL_ERROR",
            }), 500

    return require_session_identity(decorated_function)
