"""
Token validation endpoint for nginx auth_request subrequest.

Nginx calls GET /api/auth-validate/validate on every protected request.
Returns:
  - 200 + X-Authenticated-User header → valid
  - 401 → invalid (nginx handles the client-facing error response)

Validation order:
  1. Authorization: Bearer unifai_t_... → API token (MongoDB)
  2. Authorization: Bearer <session_id> → SSO session (Redis)
  3. Session cookie fallback → SSO session (Redis)
"""
import logging

from flask import Blueprint, current_app, request, session

from tokens.models import TOKEN_PREFIX
from global_utils.redis import get_identity_session

logger = logging.getLogger(__name__)

auth_validate_bp = Blueprint("auth_validate", __name__)


@auth_validate_bp.route("/validate", methods=["GET"])
def validate():
    auth_manager = current_app.extensions.get("auth_manager")
    if not auth_manager:
        return "", 500

    bearer = _extract_bearer()

    if bearer and bearer.startswith(TOKEN_PREFIX):
        user_data = _validate_api_token(bearer)
        if user_data:
            return _ok(user_data.username)
        return "", 401

    session_id = bearer or _extract_session_from_cookie()
    if not session_id:
        return "", 401

    session_data = get_identity_session(auth_manager.redis_store, session_id)
    if session_data is None or not session_data.has_auth_credentials():
        return "", 401

    username = session_data.username or ""
    if not username:
        return "", 401

    return _ok(username)


def _ok(username: str):
    response = current_app.make_response(("", 200))
    response.headers["X-Authenticated-User"] = username
    return response


def _extract_bearer() -> str | None:
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        value = auth_header[7:].strip()
        return value or None
    return None


def _extract_session_from_cookie() -> str | None:
    cookie_session_id = request.cookies.get("session") or ""
    if cookie_session_id:
        return cookie_session_id
    return session.get("session_id")


def _validate_api_token(token: str):
    """Validate an API token. Returns TokenUserData if valid, None otherwise."""
    container = getattr(current_app, "container", None)
    if not container or not hasattr(container, "token_service"):
        logger.error("Token service not configured")
        return None
    return container.token_service.validate(token)
