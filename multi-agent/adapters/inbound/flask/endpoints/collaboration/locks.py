"""
Flask collaboration endpoints — team-scoped workspace edit locks.
"""
import logging

from flask import Blueprint, current_app, jsonify
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

from inbound.flask.decorators import with_authenticated_user

logger = logging.getLogger(__name__)

collaboration_locks_bp = Blueprint("collaboration_locks", __name__)


def _collab_service():
    svc = current_app.container.collaboration_service
    if svc is None:
        return None, (jsonify(
            {"error": "Collaboration service not available - Redis is not configured"}
        ), 501)
    return svc, None


def _holder_to_json(holder):
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }


@collaboration_locks_bp.route("/edit_lock.acquire", methods=["POST"])
@with_authenticated_user
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def edit_lock_acquire(authenticated_user, team_id, entity_kind, entity_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        acquired, holder = svc.acquire_team_edit_lock(
            team_id=team_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            user_id=authenticated_user,
        )
        body = {"acquired": acquired}
        if not acquired and holder is not None:
            body["lockedBy"] = _holder_to_json(holder)
        return jsonify(body), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("edit_lock_acquire failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_locks_bp.route("/edit_lock.release", methods=["POST"])
@with_authenticated_user
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def edit_lock_release(authenticated_user, team_id, entity_kind, entity_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        svc.release_team_edit_lock(team_id, entity_kind, entity_id, authenticated_user)
        return jsonify({"success": True}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("edit_lock_release failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_locks_bp.route("/edit_lock.heartbeat", methods=["POST"])
@with_authenticated_user
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def edit_lock_heartbeat(authenticated_user, team_id, entity_kind, entity_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        renewed = svc.renew_team_edit_lock(
            team_id, entity_kind, entity_id, authenticated_user
        )
        return jsonify({"renewed": renewed}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("edit_lock_heartbeat failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_locks_bp.route("/edit_lock.status", methods=["GET"])
@with_authenticated_user
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def edit_lock_status(authenticated_user, team_id, entity_kind, entity_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        holder = svc.get_team_edit_lock(team_id, entity_kind, entity_id, authenticated_user)
        return jsonify({"locked": holder is not None, "lockedBy": _holder_to_json(holder)}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("edit_lock_status failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_locks_bp.route("/edit_lock.statuses", methods=["POST"])
@with_authenticated_user
@from_body({
    "team_id": fields.Str(data_key="teamId", required=True),
    "entity_kind": fields.Str(data_key="entityKind", required=True),
    "entity_ids": fields.List(fields.Str(), data_key="entityIds", required=True),
})
def edit_lock_statuses(authenticated_user, team_id, entity_kind, entity_ids):
    svc, err = _collab_service()
    if err:
        return err
    try:
        batch = svc.get_team_edit_locks_batch(team_id, entity_kind, entity_ids, authenticated_user)
        locks = {
            entity_id: _holder_to_json(holder) if holder is not None else None
            for entity_id, holder in batch.items()
        }
        return jsonify({"locks": locks}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("edit_lock_statuses failed")
        return jsonify({"error": "Internal server error"}), 500
