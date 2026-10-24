from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from pydantic.json import pydantic_encoder
from inbound.flask.decorators import with_require_identity_authorization, resolve_caller_scope
from mas.core.identity import Identity
import yaml
import logging

graph_validation_bp = Blueprint("graph_validation", __name__)
logger = logging.getLogger(__name__)


@graph_validation_bp.route("/names.get", methods=["GET"])
@with_require_identity_authorization
def get_validation_names(identity: Identity):
    """
    Returns the list of all available validation names.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        validation_names = validation_svc.get_validation_names()
        return jsonify({"validation_names": validation_names}), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500


@graph_validation_bp.route("/channels.validate", methods=["POST"])
@with_require_identity_authorization
def validate_channels(identity: Identity):
    """
    Validates channels for a blueprint draft YAML and returns validation report with fix suggestions.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        graph_svc = current_app.container.graph_service
        blueprint_svc = current_app.container.blueprint_service

        # Get raw YAML data from request body
        yaml_content = request.get_data(as_text=True)
        if not yaml_content:
            return jsonify({"error": "No YAML content provided in request body"}), 400

        # Parse YAML to dict and resolve blueprint
        draft_dict = yaml.safe_load(yaml_content)
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict, caller=resolve_caller_scope(identity))

        # Build graph plan and validate channels
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_channels(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500


@graph_validation_bp.route("/all.validate", methods=["POST"])
@with_require_identity_authorization
def validate_all(identity: Identity):
    """
    Runs all validations for a blueprint draft YAML and returns comprehensive validation results with fix suggestions.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        graph_svc = current_app.container.graph_service
        blueprint_svc = current_app.container.blueprint_service

        # Get raw YAML data from request body
        yaml_content = request.get_data(as_text=True)
        if not yaml_content:
            return jsonify({"error": "No YAML content provided in request body"}), 400

        # Parse YAML to dict and resolve blueprint
        draft_dict = yaml.safe_load(yaml_content)
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict, caller=resolve_caller_scope(identity))

        # Build graph plan and validate
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_result, suggestions = validation_svc.validate_and_suggest(graph_plan)

        return jsonify({
            "validation_result": validation_result.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500


@graph_validation_bp.route("/dependencies.validate", methods=["POST"])
@with_require_identity_authorization
def validate_dependencies(identity: Identity):
    """
    Validates dependencies for a blueprint draft YAML.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        graph_svc = current_app.container.graph_service
        blueprint_svc = current_app.container.blueprint_service

        # Get raw YAML data from request body
        yaml_content = request.get_data(as_text=True)
        if not yaml_content:
            return jsonify({"error": "No YAML content provided in request body"}), 400

        # Parse YAML to dict and resolve blueprint
        draft_dict = yaml.safe_load(yaml_content)
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict, caller=resolve_caller_scope(identity))

        # Build graph plan and validate dependencies
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_dependencies(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500


@graph_validation_bp.route("/cycles.validate", methods=["POST"])
@with_require_identity_authorization
def validate_cycles(identity: Identity):
    """
    Validates cycles for a blueprint draft YAML.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        graph_svc = current_app.container.graph_service
        blueprint_svc = current_app.container.blueprint_service

        # Get raw YAML data from request body
        yaml_content = request.get_data(as_text=True)
        if not yaml_content:
            return jsonify({"error": "No YAML content provided in request body"}), 400

        # Parse YAML to dict and resolve blueprint
        draft_dict = yaml.safe_load(yaml_content)
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict, caller=resolve_caller_scope(identity))

        # Build graph plan and validate cycles
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_cycles(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500


@graph_validation_bp.route("/orphans.validate", methods=["POST"])
@with_require_identity_authorization
def validate_orphans(identity: Identity):
    """
    Validates orphan nodes for a blueprint draft YAML.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        graph_svc = current_app.container.graph_service
        blueprint_svc = current_app.container.blueprint_service

        # Get raw YAML data from request body
        yaml_content = request.get_data(as_text=True)
        if not yaml_content:
            return jsonify({"error": "No YAML content provided in request body"}), 400

        # Parse YAML to dict and resolve blueprint
        draft_dict = yaml.safe_load(yaml_content)
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict, caller=resolve_caller_scope(identity))

        # Build graph plan and validate orphans
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_orphans(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500


@graph_validation_bp.route("/required_nodes.validate", methods=["POST"])
@with_require_identity_authorization
def validate_required_nodes(identity: Identity):
    """
    Validates required nodes for a blueprint draft YAML.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        graph_svc = current_app.container.graph_service
        blueprint_svc = current_app.container.blueprint_service

        # Get raw YAML data from request body
        yaml_content = request.get_data(as_text=True)
        if not yaml_content:
            return jsonify({"error": "No YAML content provided in request body"}), 400

        # Parse YAML to dict and resolve blueprint
        draft_dict = yaml.safe_load(yaml_content)
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict, caller=resolve_caller_scope(identity))

        # Build graph plan and validate required nodes
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_required_nodes(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        logger.exception("graph validation failed")
        return jsonify({"error": str(e)}), 500