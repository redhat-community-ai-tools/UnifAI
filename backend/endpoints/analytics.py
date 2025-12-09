"""
Analytics API endpoints for workflow session statistics.

Thin HTTP layer that delegates to providers/analytics.py for business logic.
"""

from flask import Blueprint, jsonify, session, request
from global_utils.helpers.apiargs import from_query
from webargs import fields
from datetime import datetime, timezone
from global_utils.config import SharedConfig
from functools import wraps
from shared.logger import logger
import time
from providers.analytics import get_workflow_analytics

analytics_bp = Blueprint("analytics", __name__)

# Get configuration for access control
config = SharedConfig.get_instance()

# NOTE: This cache is process-local. In production with multiple workers (Gunicorn/Uvicorn),
# cache hits will be inconsistent across workers. Consider using Redis or similar shared cache
# for production deployments.
_analytics_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 60,  # Cache for 60 seconds
    'cache_key': None
}


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
    Uses in-memory caching to reduce database load.
    
    Query params:
        time_range (str): Time range filter - 'today', '7days', '30days', or 'all' (default: 'all')
    """
    try:
        # Check if cache is still valid (cache key includes time_range)
        current_time = time.time()
        cache_key = time_range
        
        if (_analytics_cache.get('data') is not None and 
            _analytics_cache.get('cache_key') == cache_key and
            current_time - _analytics_cache['timestamp'] < _analytics_cache['ttl']):
            # Return cached data
            return jsonify(_analytics_cache['data']), 200
        
        # Cache miss or expired - fetch fresh data
        analytics = get_workflow_analytics()
        
        overview = {
            "total_stats": analytics.get_total_stats(),
            "status_breakdown": analytics.get_status_breakdown(),
            "time_stats": analytics.get_time_based_stats(),
            "active_today": analytics.get_active_users_today(),
            "active_7days": analytics.get_active_users(days=7),
            "active_30days": analytics.get_active_users(days=30),
            "top_users": analytics.get_user_activity(limit=10),
            "top_blueprints": analytics.get_blueprint_usage(limit=10, time_range=time_range),
            "time_series": analytics.get_time_series_activity(time_range=time_range),
            "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        # Update cache
        _analytics_cache['data'] = overview
        _analytics_cache['timestamp'] = current_time
        _analytics_cache['cache_key'] = cache_key
        
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
        analytics = get_workflow_analytics()
        active_users = analytics.get_active_users(days=days)
        
        return jsonify({
            "days": days,
            "active_users": active_users,
            "count": len(active_users)
        }), 200
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
        analytics = get_workflow_analytics()
        user_activity = analytics.get_user_activity(limit=limit)
        
        return jsonify({
            "user_activity": user_activity,
            "count": len(user_activity)
        }), 200
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
        analytics = get_workflow_analytics()
        blueprint_usage = analytics.get_blueprint_usage(limit=limit)
        
        return jsonify({
            "blueprint_usage": blueprint_usage,
            "count": len(blueprint_usage)
        }), 200
    except Exception as e:
        logger.error(f"Failed to get blueprint usage: {str(e)}")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/activity/hourly", methods=["GET"])
@require_analytics_access
@from_query({
    "days": fields.Int(data_key="days", load_default=7)
})
def get_hourly_activity(days):
    """
    Get hourly activity distribution.
    
    Query params:
        days (int): Number of days to look back (default: 7)
    """
    try:
        analytics = get_workflow_analytics()
        hourly_activity = analytics.get_hourly_activity(days=days)
        
        return jsonify({
            "days": days,
            "hourly_activity": hourly_activity
        }), 200
    except Exception as e:
        logger.error(f"Failed to get hourly activity: {str(e)}")
        return jsonify({"error": str(e)}), 500

