from flask import Blueprint, jsonify, current_app, request

from utils.caller import current_caller, require_caller

team_bp = Blueprint("teams", __name__)


def _is_member(svc, team, username: str) -> bool:
    if not username:
        return False
    if team.created_by == username:
        return True
    # Group membership is resolved from Identity's own groups cache, never
    # from request input.
    group_ids = svc.cached_group_ids(username)
    return any(
        t.team_id == team.team_id
        for t in svc.list_user_teams(username, group_ids=group_ids)
    )


def _can_access(svc, team, caller) -> bool:
    return caller.is_service or caller.is_admin or _is_member(svc, team, caller.username)


def _is_owner(team, caller) -> bool:
    """May change a team's name and member list: its creator, an admin, or the trusted service."""
    return caller.is_service or caller.is_admin or team.created_by == caller.username


def _vet_members(svc, members, caller):
    """Members a session caller proposes are untrusted input.

    A group snapshot (``group_members``) is computed by the server from the
    directory, never taken from the client, and a caller may only reference
    groups it belongs to. The trusted service and admins are not restricted.
    """
    if caller.is_service or caller.is_admin or not isinstance(members, list):
        return members
    own_groups = set(svc.cached_group_ids(caller.username) or [])
    vetted = []
    for item in members:
        if isinstance(item, dict):
            item = {k: v for k, v in item.items() if k != "group_members"}
            if item.get("type") == "group" and item.get("id") not in own_groups:
                raise ValueError("You can only add groups you belong to")
        vetted.append(item)
    return vetted


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
        team = svc.create(name=name, created_by=created_by, members=_vet_members(svc, members, caller))
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

    # Group resolution. The authority is Identity's server-side groups cache
    # (computed from the verified token / directory at login and refresh).
    # ``None`` = no group information (legacy behaviour); ``[]`` = known empty.
    cached = svc.cached_group_ids(user_id)
    group_ids = cached
    if "groupIds" in request.args:
        group_ids_str = request.args.get("groupIds", "").strip()
        requested = (
            [p.strip() for p in group_ids_str.split(",") if p.strip()]
            if group_ids_str
            else []
        )
        if caller.is_service:
            # Trusted internal caller: an explicit list is honoured as before.
            group_ids = requested
        elif cached is not None and set(requested) <= set(cached):
            # Session caller may only narrow, never widen, its cached groups.
            group_ids = requested
        # else: unverifiable or widening request -> ignored, cached groups win.

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
        caller = current_caller()
        existing = svc.get(team_id)
        if not _can_access(svc, existing, caller):
            return jsonify({"error": "Team not found"}), 404
        if not _is_owner(existing, caller):
            return jsonify({"error": "Only the team creator can change this team"}), 403
        team = svc.update(
            team_id=team_id,
            name=body.get("name"),
            members=_vet_members(svc, body.get("members"), caller),
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
        if not _can_access(svc, team, caller):
            return jsonify({"error": "Team not found"}), 404
        if team.created_by != requested_by and not caller.is_admin:
            return jsonify({"error": "Only the team creator can delete this team"}), 403

        svc.delete(team_id)
        return jsonify({"status": "deleted"}), 200
    except KeyError:
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
