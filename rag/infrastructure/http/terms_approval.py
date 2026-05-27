"""Terms approval endpoints - driving adapter."""
from flask import Blueprint, jsonify

from bootstrap.app_container import terms_approval_service
from infrastructure.http.session import with_session_user
from shared.logger import logger

terms_approval_bp = Blueprint("terms_approval", __name__)


@terms_approval_bp.route("/user.approval.status.get", methods=["GET"])
@with_session_user
def check_user_approval(username):
    """
    Check if the current user has approved the AI transparency notice.
    Username resolved from session cookie.
    """
    try:
        result = terms_approval_service().check_approval_status(username)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to check user approval for {username}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@terms_approval_bp.route("/user.approval.record.post", methods=["POST"])
@with_session_user
def approve_user(username):
    """
    Record the current user's approval of the AI transparency notice.
    Username resolved from session cookie.
    """
    try:
        result = terms_approval_service().record_approval(username)
        return jsonify({
            "status": "success",
            "message": "User approval recorded successfully",
            **result
        }), 200
    except Exception as e:
        logger.error(f"Failed to record user approval for {username}: {str(e)}")
        return jsonify({"error": str(e)}), 500
