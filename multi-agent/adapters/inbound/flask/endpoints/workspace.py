import logging

from flask import Blueprint, jsonify, current_app
from inbound.flask.decorators import with_require_team_session

logger = logging.getLogger(__name__)

workspace_bp = Blueprint("workspace", __name__)


@workspace_bp.route("/workspace.cleanup", methods=["DELETE"])
@with_require_team_session
def cleanup_workspace(identity):
    """Delete all resources, blueprints, and sessions owned by the authenticated identity."""

    container = current_app.container
    resources_deleted = container.resource_repo.delete_by_identity(identity)
    blueprints_deleted = container.blueprint_repo.delete_by_identity(identity)
    sessions_deleted = container.session_repo.delete_by_identity(identity)

    logger.info(
        "workspace.cleanup identity=%s/%s deleted resources=%d blueprints=%d sessions=%d",
        identity.type.value, identity.id,
        resources_deleted, blueprints_deleted, sessions_deleted,
    )

    return jsonify({
        "status": "cleaned",
        "identity": {"type": identity.type.value, "id": identity.id},
        "deleted": {
            "resources": resources_deleted,
            "blueprints": blueprints_deleted,
            "sessions": sessions_deleted,
        },
    }), 200
