from flask import Blueprint, jsonify, current_app, Response
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
import json
from pydantic.json import pydantic_encoder
from session.exceptions import BlueprintNotFoundError

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/user.session.create", methods=["POST"])
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "user_id": fields.Str(data_key="userId", required=True),
    "metadata": fields.Dict(data_key="metadata", required=False, load_default=lambda: {}, dump_default=lambda: {})
})
def create_user_session(blueprint_id, user_id, metadata):
    try:
        session_svc = current_app.container.session_service
        session = session_svc.create(user_id=user_id,
                                     blueprint_id=blueprint_id,
                                     metadata=metadata)
        return jsonify(session.get_run_id()), 200
    except BlueprintNotFoundError as e:
        return jsonify({
            "error": str(e), 
            "error_type": "BLUEPRINT_NOT_FOUND",
            "blueprint_id": e.blueprint_id
        }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/user.session.execute", methods=["POST"])
@from_body({
    "session_id": fields.Str(data_key="sessionId", required=True),
    "inputs": fields.Dict(data_key="inputs", required=True),
    "stream_mode": fields.List(fields.Str(), data_key="streamMode", load_default=lambda: ["custom"]),
    "stream": fields.Bool(data_key="stream", load_default=False),
    "scope": fields.Str(data_key="scope", load_default="public"),
    "logged_in_user": fields.Str(data_key="loggedInUser", required=False, load_default=lambda: "")
})
def execute_user_session(session_id, inputs, stream_mode, stream, scope, logged_in_user):
    """
    Execute (or stream) an existing session.
    - If `stream` is False (default), returns the full result as JSON.
    - If `stream` is True, returns an NDJSON stream of chunks.
    """
    svc = current_app.container.session_service

    try:
        if not stream:
            # synchronous run
            result = svc.execute(
                session_id=session_id,
                inputs=inputs,
                stream=False,
                scope=scope,
                logged_in_user=logged_in_user
            )
            return json.dumps(result, default=pydantic_encoder), 200

        # streaming run
        def generate():
            for chunk in svc.execute(
                    session_id=session_id,
                    inputs=inputs,
                    stream=True,
                    stream_mode=stream_mode,
                    scope=scope,
                    logged_in_user=logged_in_user
            ):
                # each chunk may include Pydantic models; use pydantic_encoder
                yield json.dumps(chunk, default=pydantic_encoder)

        return Response(
            generate(),
            mimetype="application/x-ndjson"
        )
    
    except BlueprintNotFoundError as e:
        return jsonify({
            "error": str(e), 
            "error_type": "BLUEPRINT_DELETED",
            "blueprint_id": e.blueprint_id,
            "session_id": e.session_id
        }), 410  # Gone
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


@sessions_bp.route("/session.user.chat.get", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def get_session_user_chat(user_id):
    try:
        svc = current_app.container.session_service
        return jsonify(svc.get_user_sessions_chat_history(user_id)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/session.user.blueprints.get", methods=["GET"])
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
})
def get_user_blueprints(user_id):
    try:
        svc = current_app.container.session_service
        return jsonify(svc.get_user_blueprints(user_id)), 200
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
    try:
        svc = current_app.container.session_service
        deleted = svc.delete(run_id=session_id)
        return jsonify({"success": deleted}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
