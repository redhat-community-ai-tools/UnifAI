from flask import Blueprint, jsonify, current_app, request

from utils.caller import current_caller, require_caller

team_bp = Blueprint("teams", __name__)


def _is_member(svc, team, username: str) -> bool:
    if not username:
        return False
    if team.created_by == username:
        return True
    return any(t.team_id == team.team_id for t in svc.list_user_teams(username))


def _can_access(svc, team, caller) -> bool:
    return caller.is_service or caller.is_admin or _is_member(svc, team, caller.username)


def _serialize_team(team):
    d = team.model_dump(mode="json")
    d["effective_member_count"] = team.effective_member_count()
    return d


@team_bp.route("/team.create", methods=["POST"])
@require_caller
def create_team():
    svc = current_app.extensions["team_service"]
    body = request.get_json(silent=True) or {}

    name = body.get("name")
    caller = current_caller()
    created_by = body.get("createdBy") if caller.is_service else caller.username
    members = body.get("members", [])

    if not name or not created_by:
        return jsonify({"error": "name and createdBy are required"}), 400

    try:
        team = svc.create(name=name, created_by=created_by, members=members)
        return jsonify(_serialize_team(team)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/teams.list", methods=["GET"])
@require_caller
def list_teams():
    svc = current_app.extensions["team_service"]
    caller = current_caller()
    user_id = request.args.get("userId", "").strip()
    if not caller.is_service:
        user_id = user_id or caller.username
        if user_id != caller.username and not caller.is_admin:
            return jsonify({"error": "Forbidden"}), 403
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400

    # ``groupIds`` omitted => unknown / legacy (do not filter by Rover groups).
    # Present but empty => caller knows the user has no Rover groups (strict).
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
@require_caller
def get_team():
    svc = current_app.extensions["team_service"]
    team_id = request.args.get("teamId", "").strip()
    if not team_id:
        return jsonify({"error": "teamId parameter is required"}), 400

    try:
        team = svc.get(team_id)
        if not _can_access(svc, team, current_caller()):
            return jsonify({"error": "Team not found"}), 404
        return jsonify(_serialize_team(team)), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@team_bp.route("/team.update", methods=["PUT"])
@require_caller
def update_team():
    svc = current_app.extensions["team_service"]
    body = request.get_json(silent=True) or {}

    team_id = body.get("teamId")
    if not team_id:
        return jsonify({"error": "teamId is required"}), 400

    try:
        if not _can_access(svc, svc.get(team_id), current_caller()):
            return jsonify({"error": "Team not found"}), 404
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
@require_caller
def delete_team():
    svc = current_app.extensions["team_service"]
    team_id = request.args.get("teamId", "").strip()
    caller = current_caller()
    requested_by = (
        request.args.get("requestedBy", "").strip() if caller.is_service else caller.username
    )
    if not team_id:
        return jsonify({"error": "teamId parameter is required"}), 400
    if not requested_by:
        return jsonify({"error": "requestedBy parameter is required"}), 400

    try:
        team = svc.get(team_id)
        if team.created_by != requested_by and not caller.is_admin:
            return jsonify({"error": "Only the team creator can delete this team"}), 403

        svc.delete(team_id)
        return jsonify({"status": "deleted"}), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
