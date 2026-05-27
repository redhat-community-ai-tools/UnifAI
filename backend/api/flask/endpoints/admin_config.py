"""
Admin Config API endpoints.

Provides REST API for admin configuration:
  GET  /api/admin_config/config.get             — full template merged with stored values
  PUT  /api/admin_config/config.section.update  — update one section's values
  GET  /api/admin_config/access.check           — check if an email has admin access
"""
from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from global_utils.flask.decorators import require_admin_access
from global_utils.redis import get_identity_username
from global_utils.redis.client import build_redis_client
from global_utils.redis.constants import SESSION_COOKIE_NAME
from webargs import fields
import logging

logger = logging.getLogger(__name__)

admin_config_bp = Blueprint("admin_config", __name__)


def _get_current_user(req):
    """Resolve current user from the unifai_session_id cookie via Redis."""
    session_id = req.cookies.get(SESSION_COOKIE_NAME, "").strip()
    if not session_id:
        return None
    return get_identity_username(build_redis_client(), session_id)

def _is_admin(user_id):
    return current_app.container.admin_config_service.is_admin(user_id)

# ─────────────────────────────────────────────────────────────────────────────
#  Read — template + stored values
# ─────────────────────────────────────────────────────────────────────────────
@admin_config_bp.route("/config.get", methods=["GET"])
@require_admin_access(_get_current_user, _is_admin)
def get_config():
    """
    Return the full admin config template merged with stored values.

    The UI uses this to render the admin configuration page dynamically.
    Requires admin access since the config may contain sensitive values
    (including the admin usernames list itself).
    """
    try:
        svc = current_app.container.admin_config_service
        config = svc.get_config()
        return jsonify(config.model_dump(mode="json")), 200
    except Exception as e:
        logger.exception("Error getting admin config")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Write — update one section
# ─────────────────────────────────────────────────────────────────────────────
@admin_config_bp.route("/config.section.update", methods=["PUT"])
@require_admin_access(_get_current_user, _is_admin)
@from_body({
    "section_key": fields.Str(data_key="sectionKey", required=True),
    "values": fields.Dict(required=True),
})
def update_section(section_key, values):
    """
    Update the stored values for a single config section.

    Body:
        sectionKey: The section key (e.g. "slack_channel_restrictions")
        values: Dict of field_key -> new value

    Returns:
        status: "success"
        on_update_action: Action identifier for downstream side-effects
                          (e.g. "clean_restricted_slack_channels"), or null.
    """
    try:
        svc = current_app.container.admin_config_service
        success, action = svc.update_section(section_key, values)

        return jsonify({
            "status": "success",
            "on_update_action": action,
        }), 200

    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Error updating admin config section '%s'", section_key)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Access check — is the current user an admin?
# ─────────────────────────────────────────────────────────────────────────────
@admin_config_bp.route("/access.check", methods=["GET"])
def access_check():
    """
    Check whether the authenticated user is in the admin_usernames list.

    Resolves username from session cookie.

    Returns:
        is_admin: bool
    """
    try:
        username = _get_current_user(request)
        if not username:
            return jsonify({"is_admin": False}), 200
        svc = current_app.container.admin_config_service
        is_admin = svc.is_admin(username)
        return jsonify({"is_admin": is_admin}), 200
    except Exception as e:
        logger.exception("Error checking admin access")
        return jsonify({"error": str(e)}), 500
