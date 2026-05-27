from flask import Blueprint, jsonify, current_app, request
from utils.auth_manager import require_auth, get_current_user

team_bp = Blueprint("teams", __name__)


def _serialize_team(team):
    d = team.model_dump(mode="json")
    d["effective_member_count"] = team.effective_member_count()
    return d


def _get_authenticated_username():
    """Return the username of the currently authenticated user, or None."""
    user = get_current_user()
    return user.get("username") if user else None


@team_bp.route("/team.create", methods=["POST"])
@require_auth
def create_team():
    svc = current_app.extensions["team_service"]
    body = request.get_json(silent=True) or {}

    name = body.get("name")
    created_by = _get_authenticated_username()
    members = body.get("members", [])

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not created_by:
        return jsonify({"error": "Could not determine authenticated user"}), 401

    try:
        team = svc.create(name=name, created_by=created_by, members=members)
        return jsonify(_serialize_team(team)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/teams.list", methods=["GET"])
def list_teams():
    """List teams for a user.

    Accepts ``userId`` as a query parameter for backward compatibility with
    server-to-server calls (e.g. MAS IdentityClient).  When omitted and a
    valid cookie session exists, the authenticated user is used instead.
    """
    svc = current_app.extensions["team_service"]
    user_id = request.args.get("userId", "").strip()

    if not user_id:
        user_id = _get_authenticated_username() or ""
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400

    if "groupIds" in request.args:
        group_ids_str = request.args.get("groupIds", "").strip()
        group_ids = (
            [p.strip() for p in group_ids_str.split(",") if p.strip()]
            if group_ids_str
            else []
        )
    else:
        group_ids = None

    try:
        teams = svc.list_user_teams(user_id, group_ids=group_ids)
        return jsonify({"teams": [_serialize_team(t) for t in teams]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.get", methods=["GET"])
def get_team():
    svc = current_app.extensions["team_service"]
    team_id = request.args.get("teamId", "").strip()
    if not team_id:
        return jsonify({"error": "teamId parameter is required"}), 400

    try:
        team = svc.get(team_id)
        return jsonify(_serialize_team(team)), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.update", methods=["PUT"])
@require_auth
def update_team():
    svc = current_app.extensions["team_service"]
    body = request.get_json(silent=True) or {}

    team_id = body.get("teamId")
    if not team_id:
        return jsonify({"error": "teamId is required"}), 400

    try:
        team = svc.update(
            team_id=team_id,
            name=body.get("name"),
            members=body.get("members"),
        )
        return jsonify(_serialize_team(team)), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.delete", methods=["DELETE"])
@require_auth
def delete_team():
    svc = current_app.extensions["team_service"]
    team_id = request.args.get("teamId", "").strip()
    if not team_id:
        return jsonify({"error": "teamId parameter is required"}), 400

    requested_by = _get_authenticated_username()
    if not requested_by:
        return jsonify({"error": "Could not determine authenticated user"}), 401

    try:
        team = svc.get(team_id)
        if team.created_by != requested_by:
            return jsonify({"error": "Only the team creator can delete this team"}), 403

        svc.delete(team_id)
        return jsonify({"status": "deleted"}), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
