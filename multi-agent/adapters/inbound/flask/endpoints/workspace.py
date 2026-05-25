import logging

from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body
from webargs import fields
from mas.core.identity import Identity, IdentityType

logger = logging.getLogger(__name__)

workspace_bp = Blueprint("workspace", __name__)


@workspace_bp.route("/workspace.cleanup", methods=["DELETE"])
@from_body({
    "identity_type": fields.Str(data_key="identityType", required=True),
    "identity_id": fields.Str(data_key="identityId", required=True),
})
def cleanup_workspace(identity_type, identity_id):
    """Delete all resources, blueprints, and sessions owned by an identity."""

    try:
        id_type = IdentityType(identity_type)
    except ValueError:
        return jsonify({"error": f"Invalid identityType: {identity_type}"}), 400

    identity = Identity(type=id_type, id=identity_id)

    container = current_app.container
    resources_deleted = container.resource_repo.delete_by_identity(identity)
    blueprints_deleted = container.blueprint_repo.delete_by_identity(identity)
    sessions_deleted = container.session_repo.delete_by_identity(identity)

    logger.info(
        "workspace.cleanup identity=%s/%s deleted resources=%d blueprints=%d sessions=%d",
        identity_type, identity_id,
        resources_deleted, blueprints_deleted, sessions_deleted,
    )

    return jsonify({
        "status": "cleaned",
        "identity": {"type": identity_type, "id": identity_id},
        "deleted": {
            "resources": resources_deleted,
            "blueprints": blueprints_deleted,
            "sessions": sessions_deleted,
        },
    }), 200
