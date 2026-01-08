from flask import Blueprint, jsonify
from webargs import fields
from global_utils.helpers.apiargs import from_query, from_body
from providers.terms_approval import check_user_approval_status, record_user_approval

terms_approval_bp = Blueprint("terms_approval", __name__)

@terms_approval_bp.route("/user.approval.status.get", methods=["GET"])
@from_query({"username": fields.Str(required=True)})
def check_user_approval(username):
    """
    Check if a user has approved the AI transparency notice.
    
    Args:
        username: Username of the current user
        
    Returns:
        JSON response indicating if user is approved
    """
    try:
        result = check_user_approval_status(username)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@terms_approval_bp.route("/user.approval.record.post", methods=["POST"])
@from_body({"username": fields.Str(required=True)})
def approve_user(username):
    """
    Record a user's approval of the AI transparency notice.
    
    Args:
        username: Username of the user who approved
        
    Returns:
        JSON response indicating success
    """
    try:
        result = record_user_approval(username)
        return jsonify({
            "status": "success",
            "message": "User approval recorded successfully",
            **result
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

