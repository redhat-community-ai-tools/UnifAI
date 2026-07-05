"""Terms approval endpoints - driving adapter."""
from flask import Blueprint, g, jsonify
from flask.wrappers import Response

from bootstrap.app_container import terms_approval_service
from infrastructure.http.auth import rag_require_session
from shared.logger import logger

terms_approval_bp = Blueprint("terms_approval", __name__)


@terms_approval_bp.route("/user.approval.status.get", methods=["GET"])
@rag_require_session
def check_user_approval() -> tuple[Response, int]:
    """
    Check if the authenticated user has approved the AI transparency notice.
        
    Returns:
        JSON response indicating if user is approved
    """
    try:
        result = terms_approval_service().check_approval_status(g.user_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to check user approval: {str(e)}")
        return jsonify({"error": str(e)}), 500


@terms_approval_bp.route("/user.approval.record.post", methods=["POST"])
@rag_require_session
def approve_user() -> tuple[Response, int]:
    """
    Record the authenticated user's approval of the AI transparency notice.
        
    Returns:
        JSON response indicating success
    """
    try:
        username = g.user_id
        result = terms_approval_service().record_approval(username)
        return jsonify({
            "status": "success",
            "message": "User approval recorded successfully",
            **result
        }), 200
    except Exception as e:
        logger.error(f"Failed to record user approval: {str(e)}")
        return jsonify({"error": str(e)}), 500
