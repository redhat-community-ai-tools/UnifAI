"""
Flask collaboration endpoints — session presence, join/leave, and typing.
"""
import logging

from flask import Blueprint, jsonify
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

from inbound.flask.decorators import bind_session_id_arg, with_authenticated_user
from inbound.flask.endpoints._collaboration_shared import collaboration_service_or_error as _collab_service

logger = logging.getLogger(__name__)

collaboration_bp = Blueprint("collaboration", __name__)


# ── Join / Leave / Heartbeat ────────────────────────────────────────

@collaboration_bp.route("/session.join", methods=["POST"])
@with_authenticated_user
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "role": fields.Str(data_key="role", load_default="collaborator"),
})
@bind_session_id_arg
def join_session(authenticated_user, session_id, role):
    svc, err = _collab_service()
    if err:
        return err
    try:
        participants = svc.join_session(
            session_id=session_id,
            user_id=authenticated_user,
            role=role,
        )
        return jsonify(participants.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": f"Session {session_id} not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("join_session failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/session.leave", methods=["POST"])
@with_authenticated_user
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
@bind_session_id_arg
def leave_session(authenticated_user, session_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        svc.leave_session(session_id=session_id, user_id=authenticated_user)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("leave_session failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/session.heartbeat", methods=["POST"])
@with_authenticated_user
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
@bind_session_id_arg
def heartbeat(authenticated_user, session_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        svc.heartbeat(session_id=session_id, user_id=authenticated_user)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("heartbeat failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Queries ─────────────────────────────────────────────────────────

@collaboration_bp.route("/session.participants", methods=["GET"])
@with_authenticated_user
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
@bind_session_id_arg
def get_participants(authenticated_user, session_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        participants = svc.get_participants(session_id, user_id=authenticated_user)
        return jsonify(participants.model_dump(mode="json")), 200
    except KeyError:
        return jsonify({"error": f"Session {session_id} not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception:
        logger.exception("get_participants failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/team.sessions", methods=["GET"])
@with_authenticated_user
@from_query({
    "team_id": fields.Str(data_key="teamId", required=True),
})
def get_team_sessions(authenticated_user, team_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        index = svc.get_team_sessions(team_id, user_id=authenticated_user)
        return jsonify(index.model_dump(mode="json")), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception:
        logger.exception("get_team_sessions failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/user.active_sessions", methods=["GET"])
@with_authenticated_user
def get_user_active_sessions(authenticated_user):
    svc, err = _collab_service()
    if err:
        return err
    try:
        session_ids = svc.get_user_active_sessions(authenticated_user)
        return jsonify({"userId": authenticated_user, "activeSessions": session_ids}), 200
    except Exception:
        logger.exception("get_user_active_sessions failed")
        return jsonify({"error": "Internal server error"}), 500


# ── Typing indicators ────────────────────────────────────────────

@collaboration_bp.route("/session.typing", methods=["POST"])
@with_authenticated_user
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "is_typing": fields.Bool(data_key="isTyping", load_default=True),
})
@bind_session_id_arg
def set_typing(authenticated_user, session_id, is_typing):
    svc, err = _collab_service()
    if err:
        return err
    try:
        if is_typing:
            svc.set_typing(session_id=session_id, user_id=authenticated_user)
        else:
            svc.clear_typing(session_id=session_id, user_id=authenticated_user)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("set_typing failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/session.typing", methods=["GET"])
@with_authenticated_user
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
@bind_session_id_arg
def get_typing(authenticated_user, session_id):
    svc, err = _collab_service()
    if err:
        return err
    try:
        users = svc.get_typing_users(session_id, user_id=authenticated_user)
        return jsonify({"sessionId": session_id, "typingUsers": users}), 200
    except KeyError:
        return jsonify({"error": f"Session {session_id} not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception:
        logger.exception("get_typing failed")
        return jsonify({"error": "Internal server error"}), 500


@collaboration_bp.route("/health", methods=["GET"])
def collaboration_health():
    svc, err = _collab_service()
    if err:
        return jsonify({"available": False, "reason": "not_configured"}), 200
    return jsonify({"available": svc.is_available()}), 200
