"""
Token validation endpoint for nginx auth_request subrequest.

Nginx calls GET /api/auth-validate/validate on every protected request.
This endpoint checks the session (from cookie or Bearer token) in Redis
and returns:
  - 200 + X-Authenticated-User header if valid
  - 401 if invalid/expired/missing

This is an internal endpoint — never called by clients directly.
"""
import logging

from flask import Blueprint, current_app, request, session

from global_utils.redis import get_identity_session
from global_utils.redis.constants import identity_session_key

logger = logging.getLogger(__name__)

auth_validate_bp = Blueprint("auth_validate", __name__)


@auth_validate_bp.route("/validate", methods=["GET"])
def validate_token():
    """Validate a session token and return the authenticated username.

    Checks in order:
      1. Authorization: Bearer <session_id> header
      2. Session cookie (session_id in Flask session)

    Returns 200 with X-Authenticated-User header on success.
    Returns 401 on failure.
    """
    auth_manager = current_app.extensions.get("auth_manager")
    if not auth_manager:
        return "", 500

    session_id = _extract_session_id()
    if not session_id:
        return "", 401

    session_data = get_identity_session(auth_manager.redis_store, session_id)
    if session_data is None or not session_data.has_auth_credentials():
        return "", 401

    username = session_data.username or ""
    if not username:
        return "", 401

    response = current_app.make_response(("", 200))
    response.headers["X-Authenticated-User"] = username
    return response


def _extract_session_id() -> str | None:
    """Extract session_id from Bearer header or cookie."""
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip() or None

    cookie_session_id = request.cookies.get("session") or ""
    if cookie_session_id:
        return cookie_session_id

    return session.get("session_id")
