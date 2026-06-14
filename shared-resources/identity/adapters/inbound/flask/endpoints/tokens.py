"""
API Token management endpoints.

All endpoints require a valid SSO session (enforced by nginx auth_request).
Delegates all business logic to TokenService.
"""
import logging

from flask import Blueprint, current_app, jsonify, request

from tokens.models import TokenUserData
from tokens.service import TokenAlreadyExistsError, TokenNotFoundError, TokenService
from global_utils.redis import get_identity_session

logger = logging.getLogger(__name__)

token_bp = Blueprint("tokens", __name__)


def _get_authenticated_user() -> str | None:
    """Get the authenticated username from header (nginx) or session (direct)."""
    header_user = request.headers.get("X-Authenticated-User", "").strip()
    if header_user:
        return header_user

    from flask import current_app, session
    from global_utils.redis import get_identity_session
    auth_manager = current_app.extensions.get("auth_manager")
    if auth_manager:
        sid = session.get("session_id")
        if sid:
            data = get_identity_session(auth_manager.redis_store, sid)
            if data and data.has_auth_credentials():
                return data.username
    return None


def get_token_service() -> TokenService:
    return current_app.container.token_service


def _get_user_data_from_session(username: str) -> TokenUserData:
    """Capture user data from the active SSO session in Redis."""
    auth_manager = current_app.extensions.get("auth_manager")
    if not auth_manager:
        return TokenUserData(username=username)

    bearer = request.headers.get("Authorization", "").strip()
    session_id = bearer[7:].strip() if bearer.startswith("Bearer ") else None

    if not session_id:
        from flask import session
        session_id = session.get("session_id")

    if not session_id:
        return TokenUserData(username=username)

    session_data = get_identity_session(auth_manager.redis_store, session_id)
    if not session_data:
        return TokenUserData(username=username)

    return TokenUserData(
        username=session_data.username or username,
        email=session_data.email or "",
        display_name=session_data.name or "",
        sub=session_data.sub or "",
    )


@token_bp.route("/create", methods=["POST"])
def create_token():
    """Create a new API token. Returns the plaintext token once."""
    username = _get_authenticated_user()
    if not username:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    user_data = _get_user_data_from_session(username)

    try:
        result = get_token_service().create(user_id=username, name=name, user_data=user_data)
        return jsonify(result.model_dump()), 201
    except TokenAlreadyExistsError as e:
        return jsonify({"error": str(e)}), 409


@token_bp.route("/list", methods=["GET"])
def list_tokens():
    """List active tokens for the authenticated user. No secrets returned."""
    username = _get_authenticated_user()
    if not username:
        return jsonify({"error": "Authentication required"}), 401

    tokens = get_token_service().list(user_id=username)
    return jsonify({
        "tokens": [
            {
                "name": t.name,
                "created_at": t.created_at.isoformat(),
                "expires_at": t.expires_at.isoformat(),
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            }
            for t in tokens
        ]
    }), 200


@token_bp.route("/revoke", methods=["POST"])
def revoke_token():
    """Revoke a token by name."""
    username = _get_authenticated_user()
    if not username:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        get_token_service().revoke(user_id=username, name=name)
        return jsonify({"revoked": True, "name": name}), 200
    except TokenNotFoundError as e:
        return jsonify({"error": str(e)}), 404
