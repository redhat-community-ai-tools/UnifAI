import logging

from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body
from webargs import fields
from inbound.flask.decorators import is_admin_user, with_authenticated_user
from mas.core.identity import Identity, IdentityType

logger = logging.getLogger(__name__)

workspace_bp = Blueprint("workspace", __name__)


@workspace_bp.route("/workspace.cleanup", methods=["DELETE"])
@with_authenticated_user
@from_body({
    "identity_type": fields.Str(data_key="identityType", required=True),
    "identity_id": fields.Str(data_key="identityId", required=True),
})
def cleanup_workspace(authenticated_user, identity_type, identity_id):
    """Delete all resources, blueprints, and sessions owned by an identity.

    Callers may clean their own workspace or that of a team they belong to;
    admins may clean any.
    """

    try:
        id_type = IdentityType(identity_type)
    except ValueError:
        return jsonify({"error": f"Invalid identityType: {identity_type}"}), 400

    identity = Identity(type=id_type, id=identity_id)

    if not _may_clean(authenticated_user, identity):
        return jsonify({"error": "Access denied"}), 403

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


def _may_clean(username: str, identity: Identity) -> bool:
    if is_admin_user(username):
        return True
    if identity.type == IdentityType.TEAM:
        provider = current_app.container.identity_provider
        if provider.is_member(username, identity.id):
            return True
        # The UI cleans up after deleting the team: an orphaned team has no
        # member left to authorize. Any lookup failure denies.
        try:
            return not provider.team_exists(identity.id)
        except Exception:
            logger.exception("team existence check failed for %s", identity.id)
            return False
    return identity.id.casefold() == username.casefold()
