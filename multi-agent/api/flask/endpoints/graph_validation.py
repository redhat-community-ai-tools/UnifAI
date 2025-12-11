from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from pydantic.json import pydantic_encoder
import yaml
import traceback

graph_validation_bp = Blueprint("graph_validation", __name__)


@graph_validation_bp.route("/names.get", methods=["GET"])
def get_validation_names():
    """
    Returns the list of all available validation names.
    """
    try:
        validation_svc = current_app.container.graph_validation_service
        validation_names = validation_svc.get_validation_names()
        return jsonify({"validation_names": validation_names}), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@graph_validation_bp.route("/channels.validate", methods=["POST"])
def validate_channels():
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
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict)

        # Build graph plan and validate channels
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_channels(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@graph_validation_bp.route("/all.validate", methods=["POST"])
def validate_all():
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
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict)

        # Build graph plan and validate
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_result, suggestions = validation_svc.validate_and_suggest(graph_plan)

        return jsonify({
            "validation_result": validation_result.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@graph_validation_bp.route("/dependencies.validate", methods=["POST"])
def validate_dependencies():
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
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict)

        # Build graph plan and validate dependencies
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_dependencies(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@graph_validation_bp.route("/cycles.validate", methods=["POST"])
def validate_cycles():
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
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict)

        # Build graph plan and validate cycles
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_cycles(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@graph_validation_bp.route("/orphans.validate", methods=["POST"])
def validate_orphans():
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
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict)

        # Build graph plan and validate orphans
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_orphans(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@graph_validation_bp.route("/required_nodes.validate", methods=["POST"])
def validate_required_nodes():
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
        blueprint_spec = blueprint_svc.resolve_draft_dict(draft_dict)

        # Build graph plan and validate required nodes
        graph_plan = graph_svc.build_plan(blueprint_spec)
        validation_report, suggestions = validation_svc.validate_required_nodes(graph_plan)

        return jsonify({
            "validation_result": validation_report.model_dump(mode="json"),
            "fix_suggestions": [suggestion.model_dump(mode="json") for suggestion in suggestions]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500