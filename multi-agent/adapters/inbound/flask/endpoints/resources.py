from flask import Blueprint, jsonify, current_app

from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.resources.errors import ResourceInUseError, BuiltInWriteProtectedError
from mas.core.enums import ResourceOwnership
from inbound.flask.decorators import (
    with_require_identity_authorization,
    with_authenticated_user,
    require_admin_access,
)

resources_bp = Blueprint("resources", __name__)


def _is_admin_user(username: str) -> bool:
    """Check if the authenticated user is in the admin_allowed_users list."""
    admin_users = current_app.config.get("admin_allowed_users", [])
    return username in admin_users


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
        resources, total_count = svc.find_resources(
            identity=identity,
            category=category,
            type=type,
            ownership=ownership,
            limit=limit,
            offset=offset,
        )
        identity_key = f"{identity.type.value}:{identity.id}"
        resources_data = []
        builtin_config_repo = current_app.container.builtin_user_config_repo
        for doc in resources:
            data = doc.model_dump(mode="json")
            if doc.ownership == ResourceOwnership.BUILTIN and builtin_config_repo:
                user_cfg = builtin_config_repo.get(doc.rid, identity_key)
                data["user_configured"] = user_cfg is not None
            resources_data.append(data)
        return jsonify({
            "resources": resources_data,
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
@with_authenticated_user
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "config": fields.Dict(required=True),
    "name": fields.Str(required=False),
})
def update_resource(authenticated_user, resource_id, config, name=None):
    svc = current_app.container.resources_service
    try:
        svc.guard_builtin_write(resource_id, _is_admin_user(authenticated_user))
        doc = svc.update(resource_id, config=config, name=name)
        return jsonify(doc.model_dump(mode="json")), 200
    except BuiltInWriteProtectedError as e:
        return jsonify({"error": str(e)}), 403
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resources_bp.route("/resource.delete", methods=["DELETE"])
@with_authenticated_user
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def delete_resource(authenticated_user, resource_id):
    svc = current_app.container.resources_service
    try:
        svc.guard_builtin_write(resource_id, _is_admin_user(authenticated_user))
        svc.delete(resource_id)
        return jsonify({"status": "deleted"}), 200
    except BuiltInWriteProtectedError as e:
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
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_builtin_schema(resource_id):
    """Get the element schema for a built-in resource with readOnly annotations.

    Returns the same config_schema as /catalog/element.spec.get but with
    each field annotated with a readOnly hint based on ReadOnlyHint annotations.
    Fields with ReadOnlyHint(read_only=False) remain editable, all others get readOnly=true.
    """
    svc = current_app.container.resources_service
    try:
        schema = svc.get_builtin_schema(resource_id)
        return jsonify(schema), 200
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

    The identity_key is derived from the caller's resolved identity:
    "user:<id>" or "team:<id>".
    """
    svc = current_app.container.resources_service
    try:
        identity_key = f"{identity.type.value}:{identity.id}"
        doc = svc.configure_builtin(
            rid=resource_id,
            identity_key=identity_key,
            config=config,
        )
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
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

    Sets ownership='builtin', visibility='public', and identity to system.
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

    Creates with system identity and visibility based on availableToAll.
    Configurable fields are derived from ReadOnlyHint annotations on the element schema.
    """
    svc = current_app.container.resources_service
    try:
        doc = svc.create_builtin(
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
        if available_to_all:
            doc = svc.promote(resource_id)
        else:
            doc = svc.demote(resource_id)
        return jsonify(doc.model_dump(mode="json")), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


