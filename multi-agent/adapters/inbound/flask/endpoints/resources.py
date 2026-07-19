import logging

from flask import Blueprint, jsonify, current_app, request, g

from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.resources.errors import (
    ResourceInUseError,
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    BuiltinConfigUnavailableError,
)
from inbound.flask.decorators import (
    with_require_identity_authorization,
    with_authenticated_user,
    require_admin_access,
    _is_admin,
    G_IDENTITY,
    G_IDENTITY_USERNAME,
)

logger = logging.getLogger(__name__)

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
@with_require_identity_authorization
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_resource(identity, resource_id):
    """Get a single resource by ID."""
    svc = current_app.container.resources_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        doc = svc.get_visible(resource_id, is_admin=_is_admin(username))
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
    "ownership": fields.Str(required=False),
    "limit": fields.Int(required=False, load_default=1000),
    "offset": fields.Int(required=False, load_default=0),
})
def list_resources(identity, category=None, type=None, ownership=None, limit=1000, offset=0):
    """
    Get resources with flexible filtering and pagination:
    - identity: scopes to user or team workspace
    - category: filter by resource category
    - category + type: filter by specific type
    - ownership: filter by ownership ('builtin' or 'custom')
    - limit/offset: pagination support
    """
    svc = current_app.container.resources_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        resources_data, total_count = svc.find_resources(
            identity=identity,
            category=category,
            type=type,
            ownership=ownership,
            limit=limit,
            offset=offset,
            is_admin=_is_admin(username),
        )
        return jsonify({
            "resources": resources_data,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(resources_data) < total_count
            }
        }), 200
    except ValueError as e:  # Invalid category enum
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.update", methods=["PUT"])
@with_require_identity_authorization
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "config": fields.Dict(required=True),
    "name": fields.Str(required=False),
})
def update_resource(identity, resource_id, config, name=None):
    svc = current_app.container.resources_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        svc.guard_write_access(resource_id, identity=identity, is_admin=_is_admin(username))
        doc = svc.update(resource_id, config=config, name=name)
        return jsonify(doc.model_dump(mode="json")), 200
    except BuiltInWriteProtectedError as e:
        return jsonify({"error": str(e)}), 403
    except ResourceAccessDeniedError as e:
        return jsonify({"error": str(e)}), 403
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.delete", methods=["DELETE"])
@with_require_identity_authorization
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def delete_resource(identity, resource_id):
    svc = current_app.container.resources_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        svc.guard_write_access(resource_id, identity=identity, is_admin=_is_admin(username))
        svc.delete(resource_id)
        return jsonify({"status": "deleted"}), 200
    except BuiltInWriteProtectedError as e:
        return jsonify({"error": str(e)}), 403
    except ResourceAccessDeniedError as e:
        return jsonify({"error": str(e)}), 403
    except ResourceInUseError as e:
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
@with_require_identity_authorization
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "user_id": fields.Str(data_key="userId", load_default=""),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
})
def validate_resource(identity, resource_id, user_id, timeout_seconds):
    """Validate a saved resource and its dependencies."""
    svc = current_app.container.resources_service
    authenticated_user = getattr(g, G_IDENTITY_USERNAME, "")
    try:
        result = svc.validate_resource(
            rid=resource_id,
            identity=identity,
            user_id=user_id,
            timeout_seconds=timeout_seconds,
            credential_user_id=authenticated_user,
            is_admin=_is_admin(authenticated_user),
        )
        return jsonify(result.model_dump()), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resources.validate", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "resource_ids": fields.List(fields.Str(), data_key="resourceIds", required=True),
    "user_id": fields.Str(data_key="userId", load_default=""),
    "timeout_seconds": fields.Float(data_key="timeoutSeconds", load_default=10.0),
    "max_workers": fields.Int(data_key="maxWorkers", load_default=10),
})
def validate_resources(identity, resource_ids, user_id, timeout_seconds, max_workers):
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
    authenticated_user = getattr(g, G_IDENTITY_USERNAME, "")

    if not resource_ids:
        return jsonify([]), 200

    max_workers = max(1, min(max_workers, 20))

    try:
        results = svc.validate_resources(
            rids=resource_ids,
            identity=identity,
            user_id=user_id,
            timeout_seconds=timeout_seconds,
            max_workers=max_workers,
            credential_user_id=authenticated_user,
            is_admin=_is_admin(authenticated_user),
        )
        return jsonify([r.model_dump() for r in results]), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.card", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_resource_card(identity, resource_id):
    """
    Get the element card for a saved resource.

    Returns the ElementCard which describes the resource's identity,
    skills, capabilities, and configuration summary.
    """
    svc = current_app.container.resources_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        card = svc.get_card(rid=resource_id, identity=identity, is_admin=_is_admin(username))
        return jsonify(card.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resources.cards", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "resource_ids": fields.List(fields.Str(), data_key="resourceIds", required=True),
})
def get_resource_cards(identity, resource_ids):
    """
    Get element cards for multiple resources.

    Returns a dictionary mapping resource IDs to their ElementCards.
    Also includes cards for any transitive dependencies. Cards reflect the
    caller's configured overlay for any built-in resources involved.
    """
    svc = current_app.container.resources_service

    if not resource_ids:
        return jsonify({}), 200

    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        cards = svc.get_cards(
            rids=resource_ids, identity=identity, is_admin=_is_admin(username),
        )
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


# ─────────────────────────────────────────────────────────────────────────────
#  Built-in resource endpoints
# ─────────────────────────────────────────────────────────────────────────────

@resources_bp.route("/builtins.list", methods=["GET"])
@require_admin_access
@from_query({
    "category": fields.Str(required=False),
    "type": fields.Str(required=False),
})
def list_builtins(category=None, type=None):
    """List all built-in resources (admin only).

    Returns all resources with ownership=builtin (public and draft),
    regardless of the caller's identity. Used by the Repository Management
    admin panel.
    """
    svc = current_app.container.resources_service
    try:
        resources = svc.find_all_builtins(category=category, type=type)
        return jsonify({
            "resources": [doc.model_dump(mode="json") for doc in resources],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/builtin.schema", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_builtin_schema(identity, resource_id):
    """Get the element schema for a built-in resource with readOnly annotations.

    Returns the same config_schema as /catalog/element.spec.get but with
    each field annotated with a readOnly hint based on ReadOnlyHint annotations.
    Fields with ReadOnlyHint(read_only=False) remain editable, all others get readOnly=true.
    Draft built-ins are only visible to admins.
    """
    svc = current_app.container.resources_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        schema = svc.get_builtin_schema(resource_id, is_admin=_is_admin(username))
        return jsonify(schema), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/builtin.user-config", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_builtin_user_config(identity, resource_id):
    """Get the current user's overlay config for a built-in resource.

    Returns the user's saved configurable-field overrides (decrypted),
    or null if the user has not configured this resource.
    """
    svc = current_app.container.resources_service
    try:
        config = svc.get_user_config(
            rid=resource_id,
            identity=identity,
        )
        return jsonify({"config": config}), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/builtin.configure", methods=["PATCH"])
@with_require_identity_authorization
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "config": fields.Dict(required=True),
})
def configure_builtin(identity, resource_id, config):
    """Save per-user/team configuration overlay for a built-in resource.

    The identity is the caller's resolved Identity object (user or team).
    """
    svc = current_app.container.resources_service
    try:
        doc = svc.configure_builtin(
            rid=resource_id,
            identity=identity,
            config=config,
        )
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except BuiltinConfigUnavailableError as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.duplicate", methods=["POST"])
@with_require_identity_authorization
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "name": fields.Str(required=True),
    "config_overrides": fields.Dict(data_key="configOverrides", load_default=None),
})
def duplicate_resource(identity, resource_id, name, config_overrides=None):
    """Duplicate a built-in resource into the caller's workspace as a custom resource.

    The clone gets ownership=custom and parent_builtin_id set to the source.
    Users can optionally override config fields (e.g. select a subset of tools).
    """
    svc = current_app.container.resources_service
    try:
        doc = svc.duplicate_builtin(
            rid=resource_id,
            identity=identity,
            name=name,
            config_overrides=config_overrides,
        )
        return jsonify(doc.model_dump(mode="json")), 201
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.promote", methods=["PATCH"])
@require_admin_access
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def promote_resource(resource_id):
    """Promote a custom resource to public built-in (admin only).

    Sets ownership='builtin' and visibility='public'. The resource's
    original owner identity is preserved (not reset to system) so all
    built-in documents keep a consistent, auditable owner.
    """
    svc = current_app.container.resources_service
    try:
        doc = svc.promote(resource_id)
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/builtin.create", methods=["POST"])
@require_admin_access
@from_body({
    "category": fields.Str(required=True),
    "type": fields.Str(required=True),
    "name": fields.Str(required=True),
    "config": fields.Dict(required=True),
    "available_to_all": fields.Bool(data_key="availableToAll", load_default=False),
})
def create_builtin_resource(
    category, type, name, config,
    available_to_all=False,
):
    """Create a resource directly as built-in (admin only).

    The creating admin's identity is preserved on the resource document
    so that all built-in resources share a consistent owner identity.
    Configurable fields are derived from ReadOnlyHint annotations on the element schema.

    Identity is read from ``g`` because ``@require_admin_access`` strips the
    ``identity`` kwarg before invoking the handler.
    """
    identity = getattr(g, G_IDENTITY)
    svc = current_app.container.resources_service
    try:
        doc = svc.create_builtin(
            identity=identity,
            category=category,
            type=type,
            name=name,
            config=config,
            available_to_all=available_to_all,
        )
        return jsonify(doc.model_dump(mode="json")), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/builtin.update", methods=["PUT"])
@require_admin_access
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "config": fields.Dict(required=False, load_default=None),
    "name": fields.Str(required=False, load_default=None),
    "available_to_all": fields.Bool(data_key="availableToAll", load_default=None),
})
def update_builtin_resource(
    resource_id, config=None, name=None,
    available_to_all=None,
):
    """Update a built-in/admin resource (admin only).

    Allows updating config, name, and availableToAll status.
    Configurable keys are derived automatically from the element schema.
    """
    svc = current_app.container.resources_service
    try:
        doc = svc.update_builtin(
            resource_id,
            config=config,
            name=name,
            available_to_all=available_to_all,
        )
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/builtin.toggle", methods=["PATCH"])
@require_admin_access
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "available_to_all": fields.Bool(data_key="availableToAll", required=True),
})
def toggle_builtin_visibility(resource_id, available_to_all):
    """Toggle visibility between public and draft (admin only).

    When toggled on (public), the resource becomes visible to all users.
    When toggled off (draft), only admins can see it in the configuration panel.
    """
    svc = current_app.container.resources_service
    try:
        doc = svc.toggle_visibility(resource_id, available_to_all=available_to_all)
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Admin edit locks (built-in resources)
#
#  Reuses the collaboration lock infrastructure with a fixed admin namespace.
#  Authorization is handled by @require_admin_access; no team membership
#  checks are needed.
# ─────────────────────────────────────────────────────────────────────────────

def _collab_service():
    svc = current_app.container.collaboration_service
    if svc is None:
        return None, (jsonify(
            {"error": "Collaboration service not available - Redis is not configured"}
        ), 501)
    return svc, None


def _holder_to_json(holder):
    if holder is None:
        return None
    return {
        "userId": holder.user_id,
        "displayName": holder.display_name or holder.user_id,
    }


@resources_bp.route("/builtin.edit_lock.acquire", methods=["POST"])
@require_admin_access
@with_authenticated_user
@from_body({
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def builtin_edit_lock_acquire(authenticated_user, entity_id):
    """Acquire an admin edit lock on a built-in resource."""
    svc, err = _collab_service()
    if err:
        return err
    try:
        acquired, holder = svc.acquire_admin_edit_lock(
            entity_id=entity_id,
            user_id=authenticated_user,
        )
        body = {"acquired": acquired}
        if not acquired and holder is not None:
            body["lockedBy"] = _holder_to_json(holder)
        return jsonify(body), 200
    except Exception:
        logger.exception("Failed to acquire admin edit lock for entity '%s'", entity_id)
        return jsonify({"error": "Internal server error"}), 500


@resources_bp.route("/builtin.edit_lock.release", methods=["POST"])
@require_admin_access
@with_authenticated_user
@from_body({
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def builtin_edit_lock_release(authenticated_user, entity_id):
    """Release an admin edit lock on a built-in resource."""
    svc, err = _collab_service()
    if err:
        return err
    try:
        svc.release_admin_edit_lock(entity_id, authenticated_user)
        return jsonify({"success": True}), 200
    except Exception:
        logger.exception("Failed to release admin edit lock for entity '%s'", entity_id)
        return jsonify({"error": "Internal server error"}), 500


@resources_bp.route("/builtin.edit_lock.heartbeat", methods=["POST"])
@require_admin_access
@with_authenticated_user
@from_body({
    "entity_id": fields.Str(data_key="entityId", required=True),
})
def builtin_edit_lock_heartbeat(authenticated_user, entity_id):
    """Renew an admin edit lock TTL on a built-in resource."""
    svc, err = _collab_service()
    if err:
        return err
    try:
        renewed = svc.renew_admin_edit_lock(entity_id, authenticated_user)
        return jsonify({"renewed": renewed}), 200
    except Exception:
        logger.exception("Failed to renew admin edit lock for entity '%s'", entity_id)
        return jsonify({"error": "Internal server error"}), 500


@resources_bp.route("/builtin.edit_lock.statuses", methods=["POST"])
@require_admin_access
@from_body({
    "entity_ids": fields.List(fields.Str(), data_key="entityIds", required=True),
})
def builtin_edit_lock_statuses(entity_ids):
    """Get lock holders for multiple built-in resources (admin only)."""
    svc, err = _collab_service()
    if err:
        return err
    try:
        batch = svc.get_admin_edit_locks_batch(entity_ids)
        locks = {
            entity_id: _holder_to_json(holder) if holder is not None else None
            for entity_id, holder in batch.items()
        }
        return jsonify({"locks": locks}), 200
    except Exception:
        logger.exception("Failed to fetch admin edit lock statuses for %s", entity_ids)
        return jsonify({"error": "Internal server error"}), 500


