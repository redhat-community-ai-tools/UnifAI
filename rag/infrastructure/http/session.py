"""
Session-based authentication for RAG endpoints.

Resolves the current username from the `unifai_session_id` cookie via Redis.
Endpoints that need the authenticated username use the `@with_session_user`
decorator which injects `username` as a keyword argument.

For internal service-to-service calls (e.g. MAS → RAG), where no browser
cookie is present, use `@with_session_user_or_internal` which allows a
query/body `loggedInUser` fallback when the cookie is absent.
"""
from functools import wraps
from typing import Callable

from flask import jsonify, request

from bootstrap.app_container import redis_client
from global_utils.redis import get_identity_username
from global_utils.redis.constants import SESSION_COOKIE_NAME


def _resolve_username_from_cookie() -> str | None:
    """Attempt to resolve username from session cookie."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    if not session_id:
        return None
    return get_identity_username(redis_client(), session_id)


def with_session_user(f: Callable) -> Callable:
    """Resolve username from session cookie and inject as `username` kwarg.

    Returns 401 if the cookie is missing or the session is invalid/expired.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        username = _resolve_username_from_cookie()
        if not username:
            return jsonify({
                "error": "Not authenticated",
                "error_type": "AUTHENTICATION_REQUIRED",
            }), 401

        kwargs["username"] = username
        return f(*args, **kwargs)
    return decorated


def with_session_user_or_internal(f: Callable) -> Callable:
    """Resolve username from session cookie; fall back to query/body param for internal calls.

    Used for endpoints called both by the UI (cookie-authenticated) and by
    internal services (MAS → RAG) which pass `loggedInUser` as a parameter.
    Returns 401 only if neither source provides a username.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        username = _resolve_username_from_cookie()
        if not username:
            body = request.get_json(silent=True) or {}
            username = (
                request.args.get("loggedInUser", "").strip()
                or body.get("logged_in_user", "").strip()
                or None
            )
        if not username:
            return jsonify({
                "error": "Not authenticated",
                "error_type": "AUTHENTICATION_REQUIRED",
            }), 401

        kwargs["username"] = username
        return f(*args, **kwargs)
    return decorated
