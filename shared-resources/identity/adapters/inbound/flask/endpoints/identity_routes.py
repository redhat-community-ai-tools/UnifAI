from flask import Blueprint, jsonify, current_app, request
from models.identity import Identity

identity_bp = Blueprint("identity", __name__)


@identity_bp.route("/identity.resolve", methods=["GET"])
def resolve_identity():
    """Resolve an identity id to its full object.

    Query params:
        id   - the identifier to look up
        type - "user" or "team" (defaults to "user")
    """
    svc = current_app.extensions["team_service"]
    identity_id = request.args.get("id", "").strip()
    identity_type = request.args.get("type", "user").strip().lower()

    if not identity_id:
        return jsonify({"error": "id parameter is required"}), 400

    try:
        if identity_type == "team":
            team = svc.get(identity_id)
            identity = Identity.team(team.team_id, display_name=team.name)
            return jsonify(identity.model_dump(mode="json")), 200

        if identity_type == "user":
            if svc.has_directory:
                token = request.headers.get("X-User-Token")
                user = svc.get_directory_user(identity_id, user_token=token)
                if user:
                    identity = Identity.user(
                        user.user_id,
                        display_name=user.display_name,
                    )
                    return jsonify(identity.model_dump(mode="json")), 200

            identity = Identity.user(identity_id)
            return jsonify(identity.model_dump(mode="json")), 200

        return jsonify({"error": f"Unknown identity type: {identity_type}"}), 400

    except KeyError:
        return jsonify({"error": "Identity not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
