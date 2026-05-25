from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_query
from webargs import fields, validate
import logging
from inbound.flask.decorators import require_admin_access, with_require_identity_authorization
from mas.statistics.models import TimeRangePreset

logger = logging.getLogger(__name__)

statistics_bp = Blueprint("statistics", __name__)


@statistics_bp.route("/stats.get", methods=["GET"])
@with_require_identity_authorization
def get_all(identity):
    """
    Get aggregated statistics for all features (identity-scoped).
    Returns all stats in a single response for optimal performance.
    """
    try:
        container = current_app.container
        statistics_service = container.statistics_service
        
        stats = statistics_service.get_all(identity)
        
        return jsonify(stats.model_dump(mode="json")), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error in get_all stats for identity %s", identity.id)
        return jsonify({"error": str(e)}), 500


@statistics_bp.route("/stats.system.get", methods=["GET"])
@require_admin_access
@from_query({
    "time_range": fields.Str(
        data_key="time_range",
        load_default=TimeRangePreset.ALL.value,
        validate=validate.OneOf(
            [preset.value for preset in TimeRangePreset],
            error="Time range must be one of {choices}"
        )
    ),
    "user_id": fields.Str(data_key="userId", required=True)
})
def get_system_stats(time_range, user_id):
    """
    Get comprehensive system-wide statistics for workflows, users, and blueprints.
    Returns all key metrics in a single response for the admin dashboard.
    
    All data is scoped to the requested time_range. The client can call this
    endpoint with different time_range values to get different views
    (e.g., today vs. last 7 days vs. all time).
    
    Requires admin access (user must be in admin_allowed_users list).
    If admin_allowed_users is empty, system stats are disabled and access is denied.
    
    Query params:
        time_range (str): Time range filter - 'today', '7days', '30days', or 'all' (default: 'all')
        userId (str, required): User ID for access control (must be in admin_allowed_users list)
    """
    try:
        container = current_app.container
        statistics_service = container.statistics_service
        
        # Convert API string to TimeRangePreset enum, then to cutoff datetime
        preset = TimeRangePreset(time_range)
        since = preset.to_since()
        
        stats = statistics_service.get_system_stats(since=since)
        
        return jsonify(stats.model_dump(mode="json")), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error in get_system_stats")
        return jsonify({"error": str(e)}), 500
