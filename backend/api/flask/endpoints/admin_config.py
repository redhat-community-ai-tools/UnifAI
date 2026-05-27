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
from webargs import fields
import logging

logger = logging.getLogger(__name__)

admin_config_bp = Blueprint("admin_config", __name__)


def _get_current_user(req):
    """Current user from X-Username/X-User-Id header (set by gateway)."""
    return req.headers.get("X-Username") or req.headers.get("X-User-Id")

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
#  Access check — is the given email an admin?
# ─────────────────────────────────────────────────────────────────────────────
@admin_config_bp.route("/access.check", methods=["GET"])
@from_query({
    "username": fields.Str(required=True),
})
def access_check(username):
    """
    Check whether *username* is in the admin_usernames list.

    Returns:
        is_admin: bool
    """
    try:
        svc = current_app.container.admin_config_service
        is_admin = svc.is_admin(username)
        return jsonify({"is_admin": is_admin}), 200
    except Exception as e:
        logger.exception("Error checking admin access")
        return jsonify({"error": str(e)}), 500
