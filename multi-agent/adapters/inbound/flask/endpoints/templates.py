"""
Template API endpoints.

Provides REST API for template operations:
- Template CRUD
- Input schema generation
- Template instantiation and materialization
"""
from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
import logging
from inbound.flask.decorators import with_require_identity_authorization

from mas.templates.errors import (
    TemplateNotFoundError,
    InstantiationError,
    MaterializationError,
)

logger = logging.getLogger(__name__)

templates_bp = Blueprint("templates", __name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Template Listing & Discovery
# ─────────────────────────────────────────────────────────────────────────────
@templates_bp.route("/templates.list", methods=["GET"])
@from_query({
    "is_public": fields.Bool(data_key="isPublic", load_default=True),
    "category": fields.Str(required=False, load_default=None),
    "tags": fields.DelimitedList(fields.Str(), data_key="tags", required=False, load_default=None),
    "skip": fields.Int(load_default=0),
    "limit": fields.Int(load_default=100),
})
def list_templates(is_public, category, tags, skip, limit):
    """
    List available templates with optional filtering.
    
    Query params:
        isPublic: Filter by public status (default: true)
        category: Filter by template category
        tags: Comma-separated list of tags to filter by
        skip: Pagination offset
        limit: Max results
    """
    try:
        svc = current_app.container.template_service
        summaries = svc.list_template_summaries(
            is_public=is_public,
            category=category,
            tags=tags,
            skip=skip,
            limit=limit,
        )
        return jsonify({
            "templates": [s.model_dump(mode="json") for s in summaries],
            "count": len(summaries),
        }), 200
    except Exception as e:
        logger.exception("Error listing templates")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/templates.search", methods=["GET"])
@from_query({
    "query": fields.Str(data_key="q", required=True),
    "limit": fields.Int(load_default=20),
})
def search_templates(query, limit):
    """
    Search templates by name/description.
    
    Query params:
        q: Search query
        limit: Max results
    """
    try:
        svc = current_app.container.template_service
        summaries = svc.search_template_summaries(query=query, limit=limit)
        return jsonify({
            "templates": [s.model_dump(mode="json") for s in summaries],
            "count": len(summaries),
        }), 200
    except Exception as e:
        logger.exception("Error searching templates")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/templates.count", methods=["GET"])
@from_query({
    "is_public": fields.Bool(data_key="isPublic", load_default=True),
    "category": fields.Str(required=False, load_default=None),
})
def count_templates(is_public, category):
    """
    Count templates matching criteria.
    """
    try:
        svc = current_app.container.template_service
        count = svc.count_templates(is_public=is_public, category=category)
        return jsonify({"count": count}), 200
    except Exception as e:
        logger.exception("Error counting templates")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Template CRUD
# ─────────────────────────────────────────────────────────────────────────────
@templates_bp.route("/template.get", methods=["GET"])
@from_query({
    "template_id": fields.Str(data_key="templateId", required=True),
})
def get_template(template_id):
    """
    Get a template by ID.
    """
    try:
        svc = current_app.container.template_service
        template = svc.get_template(template_id)
        return jsonify(template.model_dump(mode="json")), 200
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Error getting template {template_id}")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/template.summary.get", methods=["GET"])
@from_query({
    "template_id": fields.Str(data_key="templateId", required=True),
})
def get_template_summary(template_id):
    """
    Get a template summary for catalog display.
    
    Lightweight endpoint for listing views.
    """
    try:
        svc = current_app.container.template_service
        summary = svc.get_template_summary(template_id)
        return jsonify(summary.model_dump(mode="json")), 200
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Error getting template summary {template_id}")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/template.create", methods=["POST"])
@from_body({
    "draft": fields.Dict(required=True),
    "placeholders": fields.Dict(required=True),
    "metadata": fields.Dict(required=False, load_default=lambda: {}),
})
def create_template(draft, placeholders, metadata):
    """
    Create a new template.
    
    Body:
        draft: The template blueprint (BlueprintDraft format)
        placeholders: Placeholder metadata (PlaceholderMeta format)
        metadata: Optional template metadata
    """
    try:
        svc = current_app.container.template_service
        template_id = svc.create_template(
            draft=draft,
            placeholders=placeholders,
            metadata=metadata if metadata else None,
        )
        return jsonify({
            "status": "success",
            "template_id": template_id,
        }), 201
    except ValueError as e:
        return jsonify({"error": f"Invalid data: {e}"}), 400
    except Exception as e:
        logger.exception("Error creating template")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/template.delete", methods=["DELETE"])
@from_query({
    "template_id": fields.Str(data_key="templateId", required=True),
})
def delete_template(template_id):
    """
    Delete a template by ID.
    """
    # TODO: Add authorization check - verify user has permission to delete this template
    try:
        svc = current_app.container.template_service
        deleted = svc.delete_template(template_id)
        
        if deleted:
            return jsonify({
                "status": "success",
                "message": f"Template '{template_id}' deleted",
            }), 200
        else:
            return jsonify({
                "status": "error",
                "error": "Failed to delete template",
            }), 500
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Error deleting template {template_id}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Input Schema
# ─────────────────────────────────────────────────────────────────────────────
@templates_bp.route("/template.schema.get", methods=["GET"])
@from_query({
    "template_id": fields.Str(data_key="templateId", required=True),
})
def get_template_schema(template_id):
    """
    Get the input schema for a template.
    
    Returns the JSON Schema with all field definitions, types, and constraints.
    """
    try:
        svc = current_app.container.template_service
        schema = svc.get_input_schema(template_id)
        return jsonify(schema), 200
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Error getting template schema {template_id}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Input Validation
# ─────────────────────────────────────────────────────────────────────────────
@templates_bp.route("/template.input.validate", methods=["POST"])
@from_body({
    "template_id": fields.Str(data_key="templateId", required=True),
    "input": fields.Dict(required=True),
})
def validate_template_input(template_id, input):
    """
    Validate user input against a template's input schema.
    
    Use this to check input before instantiation.
    
    Returns:
        is_valid: Whether the input is valid
        errors: List of validation errors (if any)
    """
    try:
        svc = current_app.container.template_service
        result = svc.validate_input(template_id, input)
        return jsonify(result.model_dump(mode="json")), 200
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception(f"Error validating input for template {template_id}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Instantiation
# ─────────────────────────────────────────────────────────────────────────────
@templates_bp.route("/template.instantiate", methods=["POST"])
@from_body({
    "template_id": fields.Str(data_key="templateId", required=True),
    "input": fields.Dict(required=True),
})
def instantiate_template(template_id, input):
    """
    Instantiate a template with user input.
    
    Returns a valid BlueprintDraft without saving.
    """
    try:
        svc = current_app.container.template_service
        result = svc.instantiate(template_id, input)
        return jsonify(result.blueprint.model_dump(mode="json")), 200
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except InstantiationError as e:
        return jsonify({
            "error": str(e),
            "errors": e.to_dict_list(),
        }), 400
    except Exception as e:
        logger.exception(f"Error instantiating template {template_id}")
        return jsonify({"error": str(e)}), 500


@templates_bp.route("/template.materialize", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "template_id": fields.Str(data_key="templateId", required=True),
    "input": fields.Dict(required=True),
    "blueprint_name": fields.Str(data_key="blueprintName", required=False, load_default=None),
    "skip_validation": fields.Bool(data_key="skipValidation", required=False, load_default=False),
})
def materialize_template(identity, template_id, input=None,
                         blueprint_name=None, skip_validation=False):
    """
    Instantiate template and save blueprint to user's account.
    
    This is the main entry point for template usage.
    
    Args:
        templateId: Template to instantiate
        input: User-provided values for placeholders
        blueprintName: Optional name override
        skipValidation: If true, skip blueprint validation (default false)
    
    Returns:
        blueprint_id: ID of the saved blueprint
        template_id: Source template ID
        fields_filled: Number of fields that were filled
        name: Blueprint name
    """
    try:
        svc = current_app.container.template_service
        result = svc.materialize(
            template_id=template_id,
            identity=identity,
            user_input=input,
            blueprint_name=blueprint_name,
            skip_validation=skip_validation,
        )
        return jsonify({
            "status": "success",
            **result.model_dump(),
        }), 201
    except TemplateNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except InstantiationError as e:
        return jsonify({
            "error": str(e),
            "errors": e.to_dict_list(),
        }), 400
    except MaterializationError as e:
        return jsonify({
            "error": str(e),
            "errors": e.to_dict_list(),
        }), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception(f"Error materializing template {template_id}")
        return jsonify({"error": str(e)}), 500
