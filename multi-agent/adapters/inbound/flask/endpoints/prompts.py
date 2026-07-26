"""
Flask endpoints for scheduled prompts.

Provides CRUD for ScheduledPrompt entities and schedule lifecycle
operations (pause, resume, delete). All endpoints are identity-scoped.
"""
import logging

from flask import Blueprint, jsonify, current_app, g
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

from mas.prompts.service import (
    PromptLimitExceededError,
    PromptNotFoundError,
    PromptPermissionError,
)
from mas.blueprints.exceptions import BlueprintNotFoundError
from inbound.flask.decorators import with_require_identity_authorization

logger = logging.getLogger(__name__)

_RESPONSE_EXCLUDE = {"credential_user_id"}

prompts_bp = Blueprint("prompts", __name__)


@prompts_bp.route("/prompt.create", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "text": fields.Str(data_key="text", required=True),
    "inputs": fields.Dict(data_key="inputs", load_default=lambda: {}),
    "source": fields.Str(data_key="source", load_default="manual"),
    "schedule": fields.Dict(data_key="schedule", required=True),
})
def create_prompt(identity, blueprint_id, text, inputs, source, schedule):
    try:
        svc = current_app.container.prompt_service
        prompt = svc.create(
            identity=identity,
            blueprint_id=blueprint_id,
            text=text,
            inputs=inputs,
            source=source,
            schedule=schedule,
            credential_user_id=getattr(g, "identity_username", ""),
        )
        return jsonify(prompt.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 201
    except BlueprintNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "BLUEPRINT_NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except PromptLimitExceededError as e:
        return jsonify({"error": str(e), "error_type": "LIMIT_EXCEEDED"}), 409
    except ValueError as e:
        return jsonify({"error": str(e), "error_type": "VALIDATION_ERROR"}), 400
    except Exception:
        logger.exception("Unhandled error in create_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.update", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "prompt_id": fields.Str(data_key="promptId", required=True),
    "text": fields.Str(data_key="text", load_default=None),
    "inputs": fields.Dict(data_key="inputs", load_default=None),
    "schedule": fields.Dict(data_key="schedule", load_default=None),
})
def update_prompt(identity, prompt_id, text, inputs, schedule):
    try:
        svc = current_app.container.prompt_service
        prompt = svc.update(
            prompt_id,
            identity=identity,
            text=text,
            inputs=inputs,
            schedule=schedule,
        )
        return jsonify(prompt.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except ValueError as e:
        return jsonify({"error": str(e), "error_type": "VALIDATION_ERROR"}), 400
    except Exception:
        logger.exception("Unhandled error in update_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.list", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "blueprint_id": fields.Str(data_key="blueprintId", load_default=None),
})
def list_prompts(identity, blueprint_id):
    try:
        svc = current_app.container.prompt_service
        result = svc.list_enriched(identity=identity, blueprint_id=blueprint_id)
        return jsonify(result), 200
    except Exception:
        logger.exception("Unhandled error in list_prompts")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.get", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "prompt_id": fields.Str(data_key="promptId", required=True),
})
def get_prompt(identity, prompt_id):
    try:
        svc = current_app.container.prompt_service
        prompt = svc.get(prompt_id, identity=identity)
        return jsonify(prompt.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in get_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.schedule.pause", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "prompt_id": fields.Str(data_key="promptId", required=True),
})
def pause_prompt(identity, prompt_id):
    try:
        svc = current_app.container.prompt_service
        prompt = svc.pause(prompt_id, identity=identity)
        return jsonify(prompt.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in pause_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.schedule.resume", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "prompt_id": fields.Str(data_key="promptId", required=True),
})
def resume_prompt(identity, prompt_id):
    try:
        svc = current_app.container.prompt_service
        prompt = svc.resume(prompt_id, identity=identity)
        return jsonify(prompt.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in resume_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.schedule.trigger", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "prompt_id": fields.Str(data_key="promptId", required=True),
})
def trigger_prompt(identity, prompt_id):
    try:
        svc = current_app.container.prompt_service
        prompt = svc.trigger(prompt_id, identity=identity)
        return jsonify(prompt.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except ValueError as e:
        return jsonify({"error": str(e), "error_type": "VALIDATION_ERROR"}), 400
    except Exception:
        logger.exception("Unhandled error in trigger_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.delete", methods=["DELETE"])
@with_require_identity_authorization
@from_body({
    "prompt_id": fields.Str(data_key="promptId", required=True),
})
def delete_prompt(identity, prompt_id):
    try:
        svc = current_app.container.prompt_service
        svc.delete(prompt_id, identity=identity)
        return jsonify({"deleted": True}), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in delete_prompt")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@prompts_bp.route("/prompt.runs", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "prompt_id": fields.Str(data_key="promptId", required=True),
    "limit": fields.Int(data_key="limit", load_default=20),
})
def get_prompt_runs(identity, prompt_id, limit):
    try:
        svc = current_app.container.prompt_service
        runs = svc.get_runs(prompt_id, identity=identity, limit=limit)
        return jsonify([r.model_dump(mode="json") for r in runs]), 200
    except PromptNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except PromptPermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in get_prompt_runs")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500
