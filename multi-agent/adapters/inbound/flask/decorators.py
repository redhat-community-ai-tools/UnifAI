"""
Flask decorators for identity resolution and authorization.

MAS owns its own auth decorators. They read the IdentityProvider from the
application container (wired at startup) and delegate all team-membership
logic through the port — never through global_utils directly.
"""
from functools import wraps
from typing import Optional, Tuple

from flask import current_app, jsonify, request

from mas.core.identity import Identity, IdentityType, resolve_identity
from mas.core.identity.ports import IdentityProvider


# ──────────────────────────────────────────────────────────────────────────────
# Provider access
# ──────────────────────────────────────────────────────────────────────────────

def _identity_provider() -> IdentityProvider:
    """Single access point for the identity provider.

    The provider is wired at startup in the container and attached to the app.
    """
    return current_app.container.identity_provider


# ──────────────────────────────────────────────────────────────────────────────
# Request parameter extraction
# ──────────────────────────────────────────────────────────────────────────────

def _parse_identity_params(kwargs: dict) -> Tuple[str, str, str]:
    """Extract ``(user_id, identity_type, display_name)`` from the request.

    Reads from query parameters first, then JSON body, then *kwargs*
    (injected by ``@from_body`` / ``@from_query``).
    """
    body = request.get_json(silent=True) or {}
    user_id = (
        request.args.get("userId")
        or body.get("userId")
        or kwargs.get("userId")
        or kwargs.get("user_id")
        or ""
    )
    identity_type = (
        request.args.get("identityType")
        or body.get("identityType")
        or kwargs.get("identityType")
        or kwargs.get("identity_type")
        or "user"
    )
    display_name = (
        request.args.get("displayName")
        or body.get("displayName")
        or kwargs.get("displayName")
        or kwargs.get("display_name")
        or ""
    )
    return str(user_id).strip(), str(identity_type).strip().lower() or "user", str(display_name)


def _resolve_identity_or_error(kwargs: dict) -> Tuple[Optional[Identity], Optional[tuple]]:
    """Parse identity params and resolve, returning ``(identity, None)`` or ``(None, error_response)``."""
    user_id, identity_type, display_name = _parse_identity_params(kwargs)
    if not user_id:
        return None, (jsonify({"error": "userId is required"}), 400)
    try:
        return resolve_identity(user_id, identity_type, display_name), None
    except ValueError as e:
        return None, (jsonify({"error": str(e)}), 400)


# ──────────────────────────────────────────────────────────────────────────────
# Decorators
# ──────────────────────────────────────────────────────────────────────────────

def with_authenticated_user(f):
    """Extract and validate the ``X-Authenticated-User`` header.

    When the provider requires authentication, requests without the header
    receive 401. In permissive mode the header is optional (empty string
    is injected when absent).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        provider = _identity_provider()
        authenticated_user = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated_user and provider.requires_authentication:
            return jsonify({
                "error": "Missing authenticated user",
                "error_type": "AUTHENTICATION_REQUIRED",
            }), 401
        kwargs["authenticated_user"] = authenticated_user
        return f(*args, **kwargs)
    return decorated


def with_identity(f):
    """Resolve ``Identity`` from the incoming request.

    Reads ``userId``, ``identityType``, and ``displayName`` from query
    parameters or JSON body and passes the resulting ``Identity`` as
    the ``identity`` keyword argument. Returns 400 on invalid input.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        identity, err = _resolve_identity_or_error(kwargs)
        if err:
            return err
        kwargs["identity"] = identity
        return f(*args, **kwargs)
    return decorated


def with_require_identity_authorization(f):
    """Validate caller authorization AND resolve ``Identity`` in one step.

    1. Reads ``X-Authenticated-User`` from the request header.
       - If the provider requires authentication and header is missing → 401.
    2. Validates the claimed identity:
       - **user** identity: ``userId`` must match the header value → 403.
       - **team** identity: the authenticated user must be a member → 403.
    3. Resolves ``Identity`` and injects it as ``identity`` kwarg → 400 on invalid.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        provider = _identity_provider()
        user_id, identity_type_raw, _ = _parse_identity_params(kwargs)

        # ── Authentication ────────────────────────────────────────────
        authenticated_user = request.headers.get("X-Authenticated-User", "").strip()
        if not authenticated_user:
            if provider.requires_authentication:
                return jsonify({
                    "error": "Missing authenticated user",
                    "error_type": "AUTHENTICATION_REQUIRED",
                }), 401
        else:
            # ── Authorization ─────────────────────────────────────────
            if identity_type_raw == "team":
                if user_id and not provider.is_member(authenticated_user, user_id):
                    return jsonify({
                        "error": "Access denied: you are not a member of this team",
                        "error_type": "TEAM_ACCESS_DENIED",
                    }), 403
            elif user_id and user_id.casefold() != authenticated_user.casefold():
                return jsonify({
                    "error": "Access denied: userId does not match authenticated user",
                    "error_type": "USER_ACCESS_DENIED",
                }), 403

        # ── Identity resolution ───────────────────────────────────────
        identity, err = _resolve_identity_or_error(kwargs)
        if err:
            return err
        kwargs["identity"] = identity
        return f(*args, **kwargs)

    return decorated


def require_admin_access(f):
    """Gate an endpoint to users listed in ``admin_allowed_users``.

    Reads ``userId`` from kwargs (injected by ``@from_query``) or from the
    ``userId`` / ``user_id`` query parameter.
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
                kwargs.get("user_id")
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
