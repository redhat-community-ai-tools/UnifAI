from flask import Blueprint, jsonify, current_app, request

from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.resources.errors import ResourceInUseError
from inbound.flask.decorators import with_require_identity_authorization, with_authenticated_user

resources_bp = Blueprint("resources", __name__)

MAX_UPLOAD_SIZE_BYTES = 16384


@resources_bp.route("/resource.upload-file", methods=["POST"])
@with_authenticated_user
def upload_resource_file(authenticated_user):
    """Upload a file, validate its format, and return content as a string.

    Accepts multipart/form-data with:
      - file: the uploaded file
      - format: validation format (default "pem")

    Returns 200 with {content, filename, size_bytes, format_valid}
    or 400 with {error, format_valid: false}.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided", "format_valid": False}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Empty filename", "format_valid": False}), 400

    fmt = request.form.get("format", "pem")
    raw_bytes = uploaded.read()

    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        return jsonify({
            "error": f"File too large ({len(raw_bytes)} bytes). Maximum is {MAX_UPLOAD_SIZE_BYTES} bytes.",
            "format_valid": False,
        }), 400

    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({
            "error": "File is not valid UTF-8 text. Binary files are not supported.",
            "format_valid": False,
        }), 400

    content = content.replace("\r\n", "\n").rstrip()

    if fmt == "pem":
        if "-----BEGIN" not in content or "-----END" not in content:
            return jsonify({
                "error": "File does not contain valid PEM markers (-----BEGIN / -----END).",
                "format_valid": False,
            }), 400

    return jsonify({
        "content": content,
        "filename": uploaded.filename,
        "size_bytes": len(raw_bytes),
        "format_valid": True,
    }), 200


@resources_bp.route("/resource.save", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "category": fields.Str(required=True),
    "type": fields.Str(required=True),
    "name": fields.Str(required=True),
    "config": fields.Dict(required=True),
})
def save_resource(identity, category=None, type=None, name=None, config=None):
    svc = current_app.container.resources_service
    try:
        doc = svc.create(identity=identity,
                         category=category,
                         type=type,
                         name=name,
                         config=config)
        return jsonify(doc.model_dump(mode="json")), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.get", methods=["GET"])
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_resource(resource_id):
    """Get a single resource by ID."""
    svc = current_app.container.resources_service
    try:
        doc = svc.get(resource_id)
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resources.list", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "category": fields.Str(required=False),
    "type": fields.Str(required=False),
    "limit": fields.Int(required=False, load_default=1000),
    "offset": fields.Int(required=False, load_default=0),
})
def list_resources(identity, category=None, type=None, limit=1000, offset=0):
    """
    Get resources with flexible filtering and pagination:
    - identity: scopes to user or team workspace
    - category: filter by resource category
    - category + type: filter by specific type
    - limit/offset: pagination support
    """
    svc = current_app.container.resources_service
    try:
        resources, total_count = svc.find_resources(
            identity=identity,
            category=category,
            type=type,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "resources": [doc.model_dump(mode="json") for doc in resources],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(resources) < total_count
            }
        }), 200
    except ValueError as e:  # Invalid category enum
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.update", methods=["PUT"])
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "config": fields.Dict(required=True),
    "name": fields.Str(required=False),
})
def update_resource(resource_id, config, name=None):
    svc = current_app.container.resources_service
    try:
        doc = svc.update(resource_id, config=config, name=name)
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:  # unknown id
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:  # validation, duplicate name, etc.
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.delete", methods=["DELETE"])
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def delete_resource(resource_id):
    # TODO: Add authorization check - verify user has permission to delete this resource
    svc = current_app.container.resources_service
    try:
        svc.delete(resource_id)
        return jsonify({"status": "deleted"}), 200
    except ResourceInUseError as e:
        # The resource is referenced by blueprints or other resources
        return jsonify({"error": str(e),
                        "blueprints": e.by_blueprints,
                        "resources": e.by_resources}), 400
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.schema", methods=["GET"])
def get_resource_schema():
    """Get the JSON schema for Resource model."""
    svc = current_app.container.resources_service
    try:
        schema = svc.get_resource_schema()
        return jsonify(schema), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.validate", methods=["POST"])
@with_authenticated_user
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "user_id": fields.Str(data_key="userId", load_default=""),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
})
def validate_resource(authenticated_user, resource_id, user_id, timeout_seconds):
    """Validate a saved resource and its dependencies."""
    svc = current_app.container.resources_service
    try:
        result = svc.validate_resource(
            rid=resource_id,
            user_id=user_id,
            timeout_seconds=timeout_seconds,
            credential_user_id=authenticated_user,
        )
        return jsonify(result.model_dump()), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resources.validate", methods=["POST"])
@with_authenticated_user
@from_body({
    "resource_ids": fields.List(fields.Str(), data_key="resourceIds", required=True),
    "user_id": fields.Str(data_key="userId", load_default=""),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
    "max_workers": fields.Int(data_key="maxWorkers", load_default=10),
})
def validate_resources(authenticated_user, resource_ids, user_id, timeout_seconds, max_workers):
    """
    Validate multiple resources in parallel.

    Request:
        {
            "resourceIds": ["rid1", "rid2", "rid3"],
            "userId": "alice",
            "timeoutSeconds": 10.0,
            "maxWorkers": 10
        }

    Response:
        [
            { "element_rid": "rid1", "is_valid": true, ... },
            { "element_rid": "rid2", "is_valid": false, ... },
            { "element_rid": "rid3", "is_valid": true, ... }
        ]

    Results are returned in the same order as the input resourceIds.
    """
    svc = current_app.container.resources_service

    # Validate input
    if not resource_ids:
        return jsonify([]), 200

    # Cap max_workers and ensure a positive value
    max_workers = max(1, min(max_workers, 20))

    try:
        results = svc.validate_resources(
            rids=resource_ids,
            user_id=user_id,
            timeout_seconds=timeout_seconds,
            max_workers=max_workers,
            credential_user_id=authenticated_user,
        )
        return jsonify([r.model_dump() for r in results]), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.card", methods=["GET"])
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_resource_card(resource_id):
    """
    Get the element card for a saved resource.

    Returns the ElementCard which describes the resource's identity,
    skills, capabilities, and configuration summary.
    """
    svc = current_app.container.resources_service
    try:
        card = svc.get_card(rid=resource_id)
        return jsonify(card.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resources.cards", methods=["POST"])
@from_body({
    "resource_ids": fields.List(fields.Str(), data_key="resourceIds", required=True),
})
def get_resource_cards(resource_ids):
    """
    Get element cards for multiple resources.

    Returns a dictionary mapping resource IDs to their ElementCards.
    Also includes cards for any transitive dependencies.
    """
    svc = current_app.container.resources_service

    if not resource_ids:
        return jsonify({}), 200

    try:
        cards = svc.get_cards(rids=resource_ids)
        return jsonify({
            rid: card.model_dump(mode="json")
            for rid, card in cards.items()
        }), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/config.validate", methods=["POST"])
@from_body({
    "category": fields.Str(required=True),
    "type": fields.Str(required=True),
    "name": fields.Str(required=False),
    "config": fields.Dict(required=True),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
})
def validate_config(category, type, config, name=None, timeout_seconds=10.0):
    """
    Validate a resource config before saving.

    Same fields as resource.save but validates without saving to database.
    Useful for pre-save validation in the UI.
    """
    svc = current_app.container.resources_service
    try:
        result = svc.validate_config(
            category=category,
            element_type=type,
            config=config,
            name=name,
            timeout_seconds=timeout_seconds,
        )
        return jsonify(result.model_dump()), 200
    except ValueError as e:
        return jsonify({"error": f"Schema validation failed: {e}"}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
