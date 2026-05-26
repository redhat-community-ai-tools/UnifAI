from flask import Blueprint, jsonify, current_app, Response, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
import json
from pydantic.json import pydantic_encoder
from mas.core.channels import with_heartbeats
from mas.session.domain.exceptions import BlueprintNotFoundError
from mas.session.domain.models import SessionMeta
from inbound.flask.decorators import with_require_identity_authorization, with_authenticated_user

sessions_bp = Blueprint("sessions", __name__)

# Busy statuses per session type.
_PERSONAL_BUSY_STATUSES = {"QUEUED", "RUNNING"}
_SHARED_BUSY_STATUSES = {"LOCKED", "IN_USE"}


def _check_session_busy(session_id: str, session_type: str, svc):
    """Return a 409 Flask response if the session cannot be executed right now.

    For **Personal** sessions the session is busy when its status is QUEUED or
    RUNNING (standard execution in-progress states).

    For **Shared** sessions the session is busy when its status is LOCKED
    (reserved / queued for execution) or IN_USE (actively executing). Personal
    busy statuses are also checked as a fallback so that shared sessions moving
    through the normal execution pipeline are never double-started.

    Returns ``None`` when the session is free to be executed.
    """
    try:
        status = svc.get_status(session_id)
    except Exception:
        return None

    if session_type == "Shared":
        if status == "LOCKED":
            return jsonify({
                "error": f"Session {session_id} is LOCKED (queued for execution by another caller)",
                "status": status,
            }), 409
        if status == "IN_USE":
            return jsonify({
                "error": f"Session {session_id} is IN_USE (actively executing by another caller)",
                "status": status,
            }), 409
        # Also guard against normal busy states for shared sessions.
        if status in _PERSONAL_BUSY_STATUSES:
            return jsonify({
                "error": f"Session {session_id} is already {status}",
                "status": status,
            }), 409
    else:
        if status in _PERSONAL_BUSY_STATUSES:
            return jsonify({
                "error": f"Session {session_id} is already {status}",
                "status": status,
            }), 409

    return None


@sessions_bp.route("/user.session.create", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "metadata": fields.Dict(data_key="metadata", required=False, load_default=lambda: {}, dump_default=lambda: {})
})
def create_user_session(identity, blueprint_id, metadata):
    try:
        session_svc = current_app.container.session_service
        run_id = session_svc.create(identity=identity,
                                    blueprint_id=blueprint_id,
                                    metadata=metadata)
        return jsonify(run_id), 200
    except BlueprintNotFoundError as e:
        return jsonify({
            "error": str(e),
            "error_type": "BLUEPRINT_NOT_FOUND",
            "blueprint_id": e.blueprint_id
        }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/user.session.execute", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "inputs": fields.Dict(data_key="inputs", required=True),
    "stream_mode": fields.List(fields.Str(), data_key="streamMode", load_default=lambda: ["custom"]),
    "stream": fields.Bool(data_key="stream", load_default=False),
    "scope": fields.Str(data_key="scope", load_default="public"),
    "session_type": fields.Str(data_key="sessionType", load_default="Personal"),
})
def execute_user_session(identity, session_id, inputs, stream_mode, stream, scope, session_type):
    """
    Execute (or stream) an existing session.
    - If `stream` is False (default), returns the full result as JSON.
    - If `stream` is True, returns an NDJSON stream of channel events.
    - ``sessionType`` controls busy-state semantics:
      - ``"Personal"`` (default): rejects when status is QUEUED or RUNNING.
      - ``"Shared"``: rejects when status is LOCKED, IN_USE, QUEUED, or RUNNING.
    """
    logged_in_user = identity.id
    svc = current_app.container.session_service

    busy_response = _check_session_busy(session_id, session_type, svc)
    if busy_response is not None:
        return busy_response

    if not stream:
        result = svc.run(
            session_id=session_id,
            inputs=inputs,
            scope=scope,
            logged_in_user=logged_in_user,
        )
        return json.dumps(result, default=pydantic_encoder), 200

    def generate():
        stream_iter = svc.run(
            session_id=session_id,
            inputs=inputs,
            scope=scope,
            stream=True,
            logged_in_user=logged_in_user,
        )
        for chunk in with_heartbeats(stream_iter):
            yield json.dumps(chunk, default=pydantic_encoder) + "\n"

    resp = Response(
        generate(),
        mimetype="application/x-ndjson",
    )
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@sessions_bp.route("/user.session.submit", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "inputs": fields.Dict(data_key="inputs", required=True),
    "scope": fields.Str(data_key="scope", load_default="public"),
    "session_type": fields.Str(data_key="sessionType", load_default="Personal"),
})
def submit_user_session(identity, session_id, inputs, scope, session_type):
    """
    Fire-and-forget execute for Temporal-backed sessions.
    Starts the Temporal workflow in the background and returns HTTP 202
    immediately with the workflow_id – no blocking until completion.

    Poll /session.status.get?sessionId=<id> for status updates.

    ``sessionType`` controls busy-state semantics (see ``execute_user_session``).
    """
    try:
        svc = current_app.container.session_service

        busy_response = _check_session_busy(session_id, session_type, svc)
        if busy_response is not None:
            return busy_response

        workflow_id = svc.submit(
            session_id=session_id,
            inputs=inputs,
            scope=scope,
            logged_in_user=identity.id,
        )
        return jsonify({"sessionId": session_id, "workflowId": workflow_id}), 202
    except TypeError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.cancel", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def cancel_session(session_id):
    try:
        svc = current_app.container.session_service
        cancelled = svc.cancel(session_id=session_id)
        if not cancelled:
            return jsonify({
                "error": "Session is not in a cancellable state",
                "sessionId": session_id,
            }), 409
        return jsonify({"sessionId": session_id, "status": "CANCELLED"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.state.get", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_state(session_id):
    try:
        svc = current_app.container.session_service
        state = svc.get_state(run_id=session_id)
        return jsonify(state), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.chat.get", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_chat(session_id):
    try:
        svc = current_app.container.session_service
        chat = svc.get_chat(run_id=session_id)
        return jsonify(chat.model_dump(mode="json")), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.status.get", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_status(session_id):
    try:
        svc = current_app.container.session_service
        status = svc.get_status(run_id=session_id)
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.user.list", methods=["GET"])
@with_require_identity_authorization
def list_user_sessions(identity):
    try:
        svc = current_app.container.session_service
        return jsonify(svc.list_user_sessions(identity)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.user.blueprints.get", methods=["GET"])
@with_require_identity_authorization
def get_user_blueprints(identity):
    try:
        svc = current_app.container.session_service
        return jsonify(svc.get_user_blueprints(identity)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.delete", methods=["DELETE"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def delete_session(session_id):
    """
    Delete a session by session_id.
    Returns success: true if deleted, false if not found.
    """
    # TODO: Add authorization check - verify user has permission to delete this session
    try:
        svc = current_app.container.session_service
        deleted = svc.delete(run_id=session_id)
        return jsonify({"success": deleted}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Stream monitoring ----------

@sessions_bp.route("/session.stream.status", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_stream_status(session_id):
    """Return metadata about a session's event stream."""
    monitor = current_app.container.channel_factory.create_monitor()
    if monitor is None or not monitor.is_available():
        return jsonify({"error": "Stream monitoring not available — no distributed channel configured"}), 501
    try:
        status = monitor.get_status(session_id)
        if status is None:
            return jsonify({"error": f"Session {session_id} not found in stream"}), 404
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.stream.active", methods=["GET"])
def list_active_streams():
    """List all currently active (running) session streams."""
    monitor = current_app.container.channel_factory.create_monitor()
    if monitor is None or not monitor.is_available():
        return jsonify({"error": "Stream monitoring not available — no distributed channel configured"}), 501
    try:
        active = monitor.list_active()
        return jsonify({"active_sessions": active, "count": len(active)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.subscribe", methods=["GET"])
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def subscribe_session(session_id):
    """
    Stream session events as NDJSON.
    Late-joining clients receive the full event history (replay)
    followed by live events.
    """
    factory = current_app.container.channel_factory
    reader = factory.create_reader(session_id)

    if reader is None:
        return jsonify({"error": "Streaming subscribe not available — no distributed channel configured"}), 501

    def generate():
        try:
            for event in with_heartbeats(reader):
                yield json.dumps(event, default=pydantic_encoder) + "\n"
        finally:
            reader.close()

    resp = Response(
        generate(),
        mimetype="application/x-ndjson",
    )
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# ---------- Session meta ----------

@sessions_bp.route("/session.meta", methods=["GET"])
@with_authenticated_user
@from_query({
    "session_id": fields.Str(data_key="sessionId", required=True),
})
def get_session_meta(authenticated_user, session_id):
    """Return the full metadata object for a session.

    Combines the persisted ``SessionMeta`` with live presence data from the
    collaboration store when available.  The collaboration store is always
    the authoritative source for ``typing_users`` and ``participants`` — its
    values override whatever is stored in the persisted metadata so that
    callers always see the current live state.
    """
    try:
        svc = current_app.container.session_service
        meta = svc.get_meta(session_id)
        payload = meta.model_dump(mode="json")

        collab = getattr(current_app.container, "collaboration_service", None)
        if collab is not None and collab.is_available():
            # Redis is authoritative for live presence — always override Mongo.
            # (model_dump always emits the key even when None, so setdefault
            # would never trigger; an explicit assignment is required.)
            payload["typing_users"] = collab.get_typing_users(session_id)
            try:
                participants_obj = collab.get_participants(session_id, user_id=authenticated_user)
                payload["participants"] = [
                    p.user_id for p in participants_obj.participants
                ]
            except Exception:
                pass

        return jsonify({"sessionId": session_id, "meta": payload}), 200
    except KeyError:
        return jsonify({"error": f"Session {session_id} not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.meta", methods=["POST"])
@with_authenticated_user
def update_session_meta(authenticated_user):
    """Whole-replace the metadata for a session.

    Accepts the **complete** desired metadata state as JSON.  Unknown fields
    are stored verbatim (forward-compatible).  Live presence fields are synced
    to the collaboration store when it is available:

    - ``typing_users`` — the supplied list replaces the current Redis state:
      users in the new list get ``set_typing``, users who were previously
      typing but are absent from the new list get ``clear_typing``.  Sending
      an empty list therefore clears all typing indicators immediately.
    - ``participants`` — stored in the metadata payload (participant join/leave
      lifecycle is managed by the collaboration endpoints).

    Request body::

        {
          "sessionId": "<id>",
          "meta": {
            "title": "...",
            "tags": {"env": "prod"},
            "typing_users": ["alice", "bob"],
            "participants": ["alice"],
            "myCustomField": "anything"
          }
        }
    """
    try:
        body = request.get_json(silent=True) or {}
        session_id = str(body.get("sessionId") or "").strip()
        if not session_id:
            return jsonify({"error": "sessionId is required"}), 400

        raw_meta = body.get("meta")
        if raw_meta is None:
            return jsonify({"error": "meta is required"}), 400
        if not isinstance(raw_meta, dict):
            return jsonify({"error": "meta must be a JSON object"}), 400

        meta = SessionMeta.model_validate(raw_meta)

        svc = current_app.container.session_service
        stored = svc.update_meta(session_id, meta)

        # Sync typing indicators to the collaboration store.
        # Treat the supplied list as the desired state: set for users in the
        # new list, clear for users present in Redis but absent from the list.
        collab = getattr(current_app.container, "collaboration_service", None)
        if collab is not None and collab.is_available() and meta.typing_users is not None:
            new_typing = set(meta.typing_users)
            try:
                current_typing = set(collab.get_typing_users(session_id) or [])
                for user_id in current_typing - new_typing:
                    collab.clear_typing(session_id=session_id, user_id=user_id)
            except Exception:
                pass
            for user_id in new_typing:
                collab.set_typing(session_id=session_id, user_id=user_id)

        return jsonify({"sessionId": session_id, "meta": stored.model_dump(mode="json")}), 200

    except KeyError:
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
