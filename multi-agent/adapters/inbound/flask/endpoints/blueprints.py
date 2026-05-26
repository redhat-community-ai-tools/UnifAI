from flask import Blueprint, jsonify, current_app, request
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
import yaml
import logging
from werkzeug.exceptions import BadRequest
from typing import Optional
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    BlueprintSaveError,
    BlueprintMetadataError,
)
from inbound.flask.decorators import with_require_identity_authorization, with_authenticated_user

logger = logging.getLogger(__name__)

blueprints_bp = Blueprint("blueprints", __name__)


def _extract_blueprint_data(
    json_field_value: Optional[str | dict] = None,
    field_name: str = "blueprint"
) -> dict:
    """
    Extract blueprint data from various input formats.
    
    Supports (in priority order):
    1. JSON body field (string YAML/JSON or dict)
    2. Raw body (Content-Type: application/x-yaml, text/yaml, text/plain, application/json)
    3. Form-data file upload
    4. Form-data string field
    
    Args:
        json_field_value: Value from JSON body field (if provided via @from_body)
        field_name: Name of the field for form-data lookups
        
    Returns:
        Parsed blueprint as dict
        
    Raises:
        BadRequest: If no valid data found or parsing fails
    """
    raw_text: Optional[str] = None
    parsed_dict: Optional[dict] = None
    
    # Case 1: JSON body field provided
    if json_field_value is not None:
        if isinstance(json_field_value, dict):
            # Already a dict, use directly
            return json_field_value
        elif isinstance(json_field_value, str):
            raw_text = json_field_value
    
    # Case 2: Raw body with appropriate Content-Type
    if raw_text is None and request.content_type:
        content_type = request.content_type.lower()
        if any(ct in content_type for ct in ["yaml", "text/plain", "application/json"]):
            raw_text = request.get_data(as_text=True)
    
    # Case 3: Form-data file upload
    if raw_text is None and field_name in request.files:
        file = request.files[field_name]
        raw_text = file.read().decode("utf-8")
    
    # Case 4: Form-data string field
    if raw_text is None and field_name in request.form:
        raw_text = request.form[field_name]
    
    # No data found
    if raw_text is None:
        raise BadRequest(
            f"No {field_name} data provided. Send as JSON body, raw YAML/JSON, "
            "or form-data."
        )
    
    # Parse YAML/JSON string
    try:
        parsed_dict = yaml.safe_load(raw_text)
        if not isinstance(parsed_dict, dict):
            raise ValueError("Parsed content must be a dictionary/object.")
        return parsed_dict
    except yaml.YAMLError as e:
        raise BadRequest(f"Invalid YAML/JSON format: {e}")
    except Exception as e:
        raise BadRequest(f"Failed to parse {field_name} data: {e}")


@blueprints_bp.route("/available.blueprints.get", methods=["GET"])
@with_require_identity_authorization
def available_doc_list(identity):
    try:
        svc = current_app.container.blueprint_service
        docs = svc.list_draft_docs(identity=identity)
        return jsonify([doc.model_dump(mode="json") for doc in docs]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprints_bp.route("/available.blueprints.summary.get", methods=["GET"])
@with_require_identity_authorization
def available_blueprint_summaries(identity):
    """
    Return lightweight blueprint summaries (id, name, description,
    timestamps, metadata) without the full spec.
    """
    try:
        svc = current_app.container.blueprint_service
        summaries = svc.list_summaries(identity=identity)
        return jsonify([s.model_dump(mode="json") for s in summaries]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprints_bp.route("/available.blueprints.resolved.get", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "blueprint_id": fields.Str(data_key="blueprintId", required=False, load_default=None),
    "skip": fields.Int(data_key="skip", required=False, load_default=0),
    "limit": fields.Int(data_key="limit", required=False, load_default=100),
    "sort_desc": fields.Bool(data_key="sortDesc", required=False, load_default=True),
})
def available_resolved_doc_list(identity, blueprint_id=None, skip=0, limit=100, sort_desc=True):
    try:
        svc = current_app.container.blueprint_service

        # Single blueprint by ID
        if blueprint_id:
            resolved = svc.get_resolved_doc(blueprint_id=blueprint_id)
            return jsonify(resolved.model_dump(mode="json")), 200

        # Paginated list
        total = svc.count(identity=identity)
        items = svc.list_resolved_docs(
            identity=identity, skip=skip, limit=limit, sort_desc=sort_desc
        )
        return jsonify({
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "skip": skip,
            "limit": limit,
        }), 200

    except BlueprintNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprints_bp.route("/blueprint.save", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "blueprint_raw": fields.Str(data_key="blueprintRaw", required=False),
    "metadata": fields.Dict(data_key="metadata", required=False, load_default=lambda: {})
})
def save_blueprint(identity, blueprint_raw=None, metadata=None):
    """
    Save a blueprint draft.
    
    Accepts blueprint data in multiple formats:
    - JSON body: { "blueprintRaw": "<yaml or json string>", "userId": "...", "metadata": {...} }
    - Raw YAML/JSON body with Content-Type: application/x-yaml, text/yaml, or text/plain
    - Form-data: file upload or string field named 'blueprint_raw'
    """
    try:
        if metadata is None:
            metadata = {}

        parsed = _extract_blueprint_data(
            json_field_value=blueprint_raw,
            field_name="blueprint_raw"
        )
        
        svc = current_app.container.blueprint_service
        blueprint_id = svc.save_draft(identity=identity, draft_dict=parsed,
                                      metadata=metadata)

        return jsonify({
            "status": "success",
            "blueprint_id": blueprint_id
        }), 201

    except BadRequest as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except BlueprintSaveError as e:
        logger.exception("Failed to save blueprint for identity %s", identity.id)
        return jsonify({"status": "error", "error": str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error saving blueprint for identity %s", identity.id)
        return jsonify({"status": "error", "error": str(e)}), 500


@blueprints_bp.route("/blueprint.update", methods=["PUT"])
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "blueprint_raw": fields.Str(data_key="blueprintRaw", required=True),
})
def update_blueprint(blueprint_id, blueprint_raw):
    """Update an existing blueprint in-place, keeping the same ID."""
    try:
        parsed = _extract_blueprint_data(
            json_field_value=blueprint_raw,
            field_name="blueprint_raw"
        )

        svc = current_app.container.blueprint_service
        success = svc.update_draft(blueprint_id=blueprint_id, draft_dict=parsed)

        if not success:
            return jsonify({"status": "error", "error": "Failed to update blueprint"}), 500

        return jsonify({
            "status": "success",
            "blueprint_id": blueprint_id,
        }), 200

    except BlueprintNotFoundError as e:
        return jsonify({"status": "error", "error": str(e)}), 404
    except BadRequest as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        logger.exception(f"Unexpected error updating blueprint {blueprint_id}")
        return jsonify({"status": "error", "error": str(e)}), 500


@blueprints_bp.route("/blueprint.info.get", methods=["GET"])
@from_query({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True)
})
def get_blueprint_info(blueprint_id):
    """
    Get blueprint information.
    """
    try:
        svc = current_app.container.blueprint_service
        doc = svc.get_blueprint_draft_doc(blueprint_id)
        return jsonify(doc.model_dump(mode="json")), 200
    except BlueprintNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except KeyError:
        return jsonify({"error": "Blueprint not found"}), 404
    except Exception as e:
        logger.exception(f"Unexpected error getting blueprint info for {blueprint_id}")
        return jsonify({"error": str(e)}), 500


@blueprints_bp.route("/blueprint.draft.schema.get", methods=["GET"])
def blueprint_draft_schema_get():
    """
    Returns the schema for blueprint drafts.
    """
    try:
        svc = current_app.container.blueprint_service
        schema = svc.get_draft_schema()
        return jsonify(schema), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprints_bp.route("/remove.blueprint", methods=["DELETE"])
@from_query({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True)
})
def remove_blueprint(blueprint_id):
    """
    Delete a blueprint by its ID.
    """
    # TODO: Add authorization check - verify user has permission to delete this blueprint
    try:
        svc = current_app.container.blueprint_service
        
        # Check if blueprint exists before attempting deletion
        if not svc.exists(blueprint_id):
            return jsonify({
                "status": "error",
                "error": f"Blueprint with ID '{blueprint_id}' not found"
            }), 404
        
        # Attempt to delete the blueprint
        deleted = svc.delete(blueprint_id)
        
        if deleted:
            return jsonify({
                "status": "success",
                "message": f"Blueprint '{blueprint_id}' deleted successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "error": f"Failed to delete blueprint '{blueprint_id}'"
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@blueprints_bp.route("/blueprint.metadata.set", methods=["PUT"])
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "metadata": fields.Dict(required=True),
})
def set_metadata(blueprint_id, metadata):
    """
    Set the metadata dictionary for a blueprint.
    """
    try:
        svc = current_app.container.blueprint_service
        success = svc.set_metadata(blueprint_id=blueprint_id, metadata=metadata)
        
        if not success:
            return jsonify({"error": "Failed to update metadata"}), 500
        
        return jsonify({"status": "success"}), 200
    except BlueprintNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except BlueprintMetadataError as e:
        logger.exception(f"Failed to update metadata for blueprint {blueprint_id}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception(f"Unexpected error updating metadata for blueprint {blueprint_id}")
        return jsonify({"error": str(e)}), 500

@blueprints_bp.route("/blueprint.validate", methods=["POST"])
@with_authenticated_user
@from_body({
    "blueprint_id": fields.Str(data_key="blueprintId", required=True),
    "user_id": fields.Str(data_key="userId", load_default=""),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
})
def validate_blueprint(authenticated_user, blueprint_id, user_id, timeout_seconds):
    """Validate all elements in a saved blueprint."""
    svc = current_app.container.blueprint_service
    try:
        result = svc.validate_blueprint(
            blueprint_id=blueprint_id,
            user_id=user_id,
            timeout_seconds=timeout_seconds,
            credential_user_id=authenticated_user,
        )
        return jsonify(result.model_dump()), 200
    except BlueprintNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except KeyError as e:
        return jsonify({"error": f"Blueprint not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception(f"Unexpected error validating blueprint {blueprint_id}")
        return jsonify({"error": str(e)}), 500


@blueprints_bp.route("/draft.validate", methods=["POST"])
@from_body({
    "draft": fields.Str(required=False),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
})
def validate_draft(draft=None, timeout_seconds=10.0):
    """
    Validate a blueprint draft before saving.
    
    Validates the blueprint without saving to database.
    Useful for pre-save validation in the UI.
    
    Accepts draft data in multiple formats:
    - JSON body: { "draft": "<yaml or json string>", "timeoutSeconds": 10 }
    - Raw YAML/JSON body with Content-Type: application/x-yaml, text/yaml, or text/plain
    - Form-data: file upload or string field named 'draft'
    """
    svc = current_app.container.blueprint_service
    try:
        parsed = _extract_blueprint_data(
            json_field_value=draft,
            field_name="draft"
        )
        
        result = svc.validate_draft(
            draft_dict=parsed,
            timeout_seconds=timeout_seconds,
        )
        return jsonify(result.model_dump()), 200
        
    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": f"Schema validation failed: {e}"}), 400
    except KeyError as e:
        return jsonify({"error": f"Referenced resource not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
