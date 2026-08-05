"""
Flask endpoints for workflow schedules.

Provides CRUD for WorkflowSchedule entities and schedule lifecycle
operations (pause, resume, trigger, delete). All endpoints are identity-scoped.
"""
import logging

from flask import Blueprint, jsonify, current_app, g
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

from mas.scheduling.service import (
    ScheduleLimitExceededError,
    ScheduleNotFoundError,
    SchedulePermissionError,
)
from mas.blueprints.exceptions import BlueprintNotFoundError
from inbound.flask.decorators import with_require_identity_authorization

logger = logging.getLogger(__name__)

_RESPONSE_EXCLUDE = {"credential_user_id"}

schedules_bp = Blueprint("schedules", __name__)


@schedules_bp.route("/schedule.create", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "inputs": fields.Dict(data_key="inputs", required=True),
    "source": fields.Str(data_key="source", load_default="manual"),
    "schedule": fields.Dict(data_key="schedule", required=True),
})
def create_schedule(identity, blueprint_id, inputs, source, schedule):
    try:
        svc = current_app.container.schedule_service
        wf_schedule = svc.create(
            identity=identity,
            blueprint_id=blueprint_id,
            inputs=inputs,
            source=source,
            schedule=schedule,
            credential_user_id=getattr(g, "identity_username", ""),
        )
        return jsonify(wf_schedule.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 201
    except BlueprintNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "BLUEPRINT_NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except ScheduleLimitExceededError as e:
        return jsonify({"error": str(e), "error_type": "LIMIT_EXCEEDED"}), 409
    except ValueError as e:
        return jsonify({"error": str(e), "error_type": "VALIDATION_ERROR"}), 400
    except Exception:
        logger.exception("Unhandled error in create_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.update", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
    "inputs": fields.Dict(data_key="inputs", load_default=None),
    "schedule": fields.Dict(data_key="schedule", load_default=None),
})
def update_schedule(identity, schedule_id, inputs, schedule):
    try:
        svc = current_app.container.schedule_service
        wf_schedule = svc.update(
            schedule_id,
            identity=identity,
            inputs=inputs,
            schedule=schedule,
        )
        return jsonify(wf_schedule.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except ValueError as e:
        return jsonify({"error": str(e), "error_type": "VALIDATION_ERROR"}), 400
    except Exception:
        logger.exception("Unhandled error in update_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.list", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "blueprint_id": fields.Str(data_key="blueprintId", load_default=None),
})
def list_schedules(identity, blueprint_id):
    try:
        svc = current_app.container.schedule_service
        result = svc.list_enriched(identity=identity, blueprint_id=blueprint_id)
        return jsonify(result), 200
    except Exception:
        logger.exception("Unhandled error in list_schedules")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.get", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
})
def get_schedule(identity, schedule_id):
    try:
        svc = current_app.container.schedule_service
        wf_schedule = svc.get(schedule_id, identity=identity)
        return jsonify(wf_schedule.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in get_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.pause", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
})
def pause_schedule(identity, schedule_id):
    try:
        svc = current_app.container.schedule_service
        wf_schedule = svc.pause(schedule_id, identity=identity)
        return jsonify(wf_schedule.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in pause_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.resume", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
})
def resume_schedule(identity, schedule_id):
    try:
        svc = current_app.container.schedule_service
        wf_schedule = svc.resume(schedule_id, identity=identity)
        return jsonify(wf_schedule.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in resume_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.trigger", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
})
def trigger_schedule(identity, schedule_id):
    try:
        svc = current_app.container.schedule_service
        wf_schedule = svc.trigger(schedule_id, identity=identity)
        return jsonify(wf_schedule.model_dump(mode="json", exclude=_RESPONSE_EXCLUDE)), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except ValueError as e:
        return jsonify({"error": str(e), "error_type": "VALIDATION_ERROR"}), 400
    except Exception:
        logger.exception("Unhandled error in trigger_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.delete", methods=["DELETE"])
@with_require_identity_authorization
@from_body({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
})
def delete_schedule(identity, schedule_id):
    try:
        svc = current_app.container.schedule_service
        svc.delete(schedule_id, identity=identity)
        return jsonify({"deleted": True}), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in delete_schedule")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500


@schedules_bp.route("/schedule.runs", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "schedule_id": fields.Str(data_key="scheduleId", required=True),
    "limit": fields.Int(data_key="limit", load_default=20),
})
def get_schedule_runs(identity, schedule_id, limit):
    try:
        svc = current_app.container.schedule_service
        runs = svc.get_runs(schedule_id, identity=identity, limit=limit)
        return jsonify([r.model_dump(mode="json") for r in runs]), 200
    except ScheduleNotFoundError as e:
        return jsonify({"error": str(e), "error_type": "NOT_FOUND"}), 404
    except SchedulePermissionError as e:
        return jsonify({"error": str(e), "error_type": "FORBIDDEN"}), 403
    except Exception:
        logger.exception("Unhandled error in get_schedule_runs")
        return jsonify({"error": "Internal server error", "error_type": "INTERNAL_ERROR"}), 500
