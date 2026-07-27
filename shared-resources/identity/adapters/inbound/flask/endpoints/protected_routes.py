from flask import Blueprint, jsonify
from utils.auth_manager import require_auth, get_current_user

# Create a blueprint for protected routes
protected_bp = Blueprint('protected', __name__)

@protected_bp.route('/user.profile')
@require_auth
def get_user_profile():
    """Get current user profile information"""
    user = get_current_user()
    return jsonify({
        'profile': user,
        'message': 'Successfully retrieved user profile'
    })