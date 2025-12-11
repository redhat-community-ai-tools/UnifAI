"""
Analytics API endpoints for workflow session statistics.

Provides real-time analytics data fetched directly from MongoDB.
Uses MongoDB as shared cache across all workers.
Cache is refreshed in background by Celery workers.
"""

from flask import Blueprint, jsonify, session, request
from global_utils.helpers.apiargs import from_query
from webargs import fields
from global_utils.config import SharedConfig
from functools import wraps
from shared.logger import logger
from providers.analytics import (
    get_analytics_overview,
    get_active_users_data,
    get_user_activity_data,
    get_blueprint_usage_data
)

analytics_bp = Blueprint("analytics", __name__)

# Get configuration for access control
config = SharedConfig.get_instance()


def require_analytics_access(f):
    """Decorator to check if user has analytics access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get user from session or request headers
        user_id = None
        
        # Try to get user from Flask session (works if session is set in this backend)
        if session and 'user' in session:
            user_data = session.get('user', {})
            if isinstance(user_data, dict):
                user_id = user_data.get('username') or user_data.get('user_id') or user_data.get('preferred_username')
            elif isinstance(user_data, str):
                user_id = user_data
        
        # Fallback: try to get from request headers (if passed by proxy/auth middleware)
        if not user_id:
            user_id = (
                request.headers.get('X-User-Id') or 
                request.headers.get('X-Username') or 
                request.headers.get('X-User')
            )
        
        # Get allowed users from config
        admin_allowed_users = getattr(config, 'admin_allowed_users', [])
        if not admin_allowed_users:
            admin_allowed_users = ["yhabushi"]  # Default fallback
        
        # If we found a user, check if they're in the allowed list
        if user_id:
            if user_id not in admin_allowed_users:
                return jsonify({
                    "error": "Access denied",
                    "message": f"User '{user_id}' does not have permission to access analytics"
                }), 403
        return f(*args, **kwargs)
    return decorated_function




@analytics_bp.route("/overview", methods=["GET"])
@require_analytics_access
@from_query({
    "time_range": fields.Str(data_key="time_range", load_default="all", validate=lambda x: x in ["today", "7days", "30days", "all"])
})
def get_overview(time_range):
    """
    Get comprehensive overview of all analytics.
    
    Returns all key metrics in a single request for the dashboard.
    Uses MongoDB as shared cache across all workers.
    Cache is refreshed in background by Celery workers.
    
    Query params:
        time_range (str): Time range filter - 'today', '7days', '30days', or 'all' (default: 'all')
    """
    try:
        # Get overview from provider (handles caching and Celery refresh internally)
        overview = get_analytics_overview(time_range)
        return jsonify(overview), 200
        
    except Exception as e:
        logger.error(f"Failed to get analytics overview: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/users/active", methods=["GET"])
@require_analytics_access
@from_query({
    "days": fields.Int(data_key="days", load_default=7)
})
def get_active_users(days):
    """
    Get active users for the specified number of days.
    
    Query params:
        days (int): Number of days to look back (default: 7)
    """
    try:
        result = get_active_users_data(days=days)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to get active users: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/users/activity", methods=["GET"])
@require_analytics_access
@from_query({
    "limit": fields.Int(data_key="limit", load_default=15)
})
def get_user_activity(limit):
    """
    Get detailed user activity breakdown.
    
    Query params:
        limit (int): Number of top users to return (default: 15)
    """
    try:
        result = get_user_activity_data(limit=limit)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to get user activity: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/blueprints/usage", methods=["GET"])
@require_analytics_access
@from_query({
    "limit": fields.Int(data_key="limit", load_default=10)
})
def get_blueprint_usage(limit):
    """
    Get most used blueprints.
    
    Query params:
        limit (int): Number of top blueprints to return (default: 10)
    """
    try:
        result = get_blueprint_usage_data(limit=limit)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to get blueprint usage: {str(e)}")
        return jsonify({"error": str(e)}), 500

