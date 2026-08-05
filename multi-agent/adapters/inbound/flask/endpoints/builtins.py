"""Built-in resource endpoints: admin lifecycle, per-identity overlays, and
admin edit locks.

Split out of ``resources.py`` to keep that module scoped to core
resource CRUD/validation/cards, while this module owns the built-in-specific
surface area (admin create/update/toggle, schema exposure, user overlays).
Registered under the same ``/api/resources`` URL prefix as ``resources_bp``
(see ``endpoints/__init__.py``), so the API contract is unchanged for
clients.
"""
import logging

from flask import Blueprint, jsonify, current_app, g

from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    BuiltinConfigUnavailableError,
    BuiltinDependentsPublicError,
)
from inbound.flask.decorators import (
    with_require_identity_authorization,
    with_authenticated_user,
    require_admin_access,
    is_admin_user,
    G_IDENTITY,
    G_IDENTITY_USERNAME,
)
from inbound.flask.endpoints._collaboration_shared import (
    collaboration_service_or_error as _collab_service,
    holder_to_json as _holder_to_json,
    reject_if_locked_by_other as _reject_if_locked_by_other,
)
from mas.resources.builtin_models import BuiltinUpdateRequest

logger = logging.getLogger(__name__)

builtins_bp = Blueprint("builtins", __name__)


def _resource_summaries(resources) -> list:
    """Minimal {rid, name, category} summaries for cascade/dependent lists."""
    return [
        {
            "rid": r.rid,
            "name": r.name,
            "category": r.category.value if hasattr(r.category, "value") else r.category,
        }
        for r in resources
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  Built-in resource endpoints
# ─────────────────────────────────────────────────────────────────────────────

@builtins_bp.route("/builtins.list", methods=["GET"])
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
    svc = current_app.container.builtin_resource_service
    resources_svc = current_app.container.resources_service
    try:
        resources = svc.find_all_builtins(category=category, type=type)
        return jsonify({
            "resources": [resources_svc.to_dict(doc) for doc in resources],
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to list built-in resources")
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.schema", methods=["GET"])
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
    svc = current_app.container.builtin_resource_service
    try:
        username = getattr(g, G_IDENTITY_USERNAME, "")
        schema = svc.get_builtin_schema(resource_id, is_admin=is_admin_user(username))
        return jsonify(schema), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except BuiltInWriteProtectedError as e:
        return jsonify({"error": str(e)}), 403
    except ResourceAccessDeniedError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to get schema for built-in resource '%s'", resource_id)
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.user-config", methods=["GET"])
@with_require_identity_authorization
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def get_builtin_user_config(identity, resource_id):
    """Get the current user's overlay config for a built-in resource.

    Returns the user's saved configurable-field overrides (decrypted),
    or null if the user has not configured this resource.
    """
    svc = current_app.container.builtin_resource_service
    try:
        config = svc.get_user_config(
            rid=resource_id,
            identity=identity,
        )
        return jsonify({"config": config}), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except BuiltinConfigUnavailableError as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to get user config for built-in resource '%s'", resource_id)
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.configure", methods=["PATCH"])
@with_require_identity_authorization
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "config": fields.Dict(required=True),
})
def configure_builtin(identity, resource_id, config):
    """Save per-user/team configuration overlay for a built-in resource.

    The identity is the caller's resolved Identity object (user or team).
    """
    svc = current_app.container.builtin_resource_service
    try:
        doc = svc.configure_builtin(
            rid=resource_id,
            identity=identity,
            config=config,
        )
        return jsonify(current_app.container.resources_service.to_dict(doc)), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except BuiltinConfigUnavailableError as e:
        return jsonify({"error": str(e)}), 503
    except (BuiltInWriteProtectedError, ResourceAccessDeniedError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to configure built-in resource '%s'", resource_id)
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.cascade-preview", methods=["GET"])
@require_admin_access
@from_query({
    "resource_id": fields.Str(data_key="resourceId", required=True),
})
def preview_builtin_cascade(resource_id):
    """Preview which resources would be newly promoted to public if
    *resource_id* were made available to all (admin only).

    Read-only — does not mutate anything. Lets the admin UI show a
    confirmation dialog listing everything that will be swept along
    *before* the promote/toggle mutation happens, instead of only
    disclaiming the side effect afterward in a success toast.
    """
    svc = current_app.container.builtin_resource_service
    try:
        cascaded = svc.preview_cascade_targets(resource_id)
        return jsonify({"cascaded_resources": _resource_summaries(cascaded)}), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to preview cascade for resource '%s'", resource_id)
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.create", methods=["POST"])
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

    If ``availableToAll`` is set and the config references other resources
    (e.g. an agent's LLM/provider/tool refs) that aren't already public
    built-ins, those are promoted alongside it and reported back as
    ``cascaded_resources``.
    """
    identity = getattr(g, G_IDENTITY)
    svc = current_app.container.builtin_resource_service
    try:
        doc, cascaded = svc.create_builtin_with_cascade(
            identity=identity,
            category=category,
            type=type,
            name=name,
            config=config,
            available_to_all=available_to_all,
        )
        response = current_app.container.resources_service.to_dict(doc)
        if cascaded:
            response["cascaded_resources"] = _resource_summaries(cascaded)
        return jsonify(response), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to create built-in resource '%s'", name)
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.update", methods=["PUT"])
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

    Turning ``availableToAll`` on cascades to any not-yet-public aggregated
    elements (reported as ``cascaded_resources``). Turning it off is
    rejected with ``BuiltinDependentsPublicError`` if a public built-in
    still aggregates this resource.

    Rejected with 409 if another admin currently holds the edit lock on
    this resource.
    """
    lock_error = _reject_if_locked_by_other(resource_id)
    if lock_error:
        return lock_error
    svc = current_app.container.builtin_resource_service
    try:
        update = BuiltinUpdateRequest(
            config=config, name=name, available_to_all=available_to_all,
        )
        doc, cascaded = svc.update_builtin_with_cascade(resource_id, update=update)
        response = current_app.container.resources_service.to_dict(doc)
        if cascaded:
            response["cascaded_resources"] = _resource_summaries(cascaded)
        return jsonify(response), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except BuiltinDependentsPublicError as e:
        return jsonify({
            "error": str(e),
            "dependents": _resource_summaries(e.dependents),
        }), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to update built-in resource '%s'", resource_id)
        return jsonify({"error": "Internal server error"}), 500


@builtins_bp.route("/builtin.toggle", methods=["PATCH"])
@require_admin_access
@from_body({
    "resource_id": fields.Str(data_key="resourceId", required=True),
    "available_to_all": fields.Bool(data_key="availableToAll", required=True),
})
def toggle_builtin_visibility(resource_id, available_to_all):
    """Toggle visibility between public and draft (admin only).

    When toggled on (public), the resource becomes visible to all users.
    Any element it aggregates (LLMs, providers, tools, etc.) that isn't
    already a public built-in is promoted alongside it — reported back as
    ``cascaded_resources`` so the UI can disclaim the side effect.

    When toggled off (draft), only admins can see it in the configuration
    panel. This is rejected with a 400 (``BuiltinDependentsPublicError``)
    if a public built-in (e.g. an "available to all" agent) still
    aggregates this resource — it must be demoted first, or reconfigured
    to use a different element.

    Rejected with 409 if another admin currently holds the edit lock on
    this resource.
    """
    lock_error = _reject_if_locked_by_other(resource_id)
    if lock_error:
        return lock_error
    svc = current_app.container.builtin_resource_service
    try:
        doc, cascaded = svc.toggle_visibility_with_cascade(resource_id, available_to_all=available_to_all)
        response = current_app.container.resources_service.to_dict(doc)
        if cascaded:
            response["cascaded_resources"] = _resource_summaries(cascaded)
        return jsonify(response), 200
    except KeyError as e:
        return jsonify({"error": f"Resource not found: {e}"}), 404
    except BuiltinDependentsPublicError as e:
        return jsonify({
            "error": str(e),
            "dependents": _resource_summaries(e.dependents),
        }), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Failed to toggle visibility for built-in resource '%s'", resource_id)
        return jsonify({"error": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Admin edit locks (built-in resources)
#
#  Reuses the collaboration lock infrastructure with a fixed admin namespace.
#  Authorization is handled by @require_admin_access; no team membership
#  checks are needed.
#
#  Enforcement: acquiring a lock is cooperative (the UI does it before
#  opening the edit form), but the mutating endpoints above
#  (builtin.update, builtin.toggle) as well as the
#  generic resource.update/resource.delete routes in resources.py (which
#  admins also use to mutate built-in resources) call
#  ``reject_if_locked_by_other`` (see ``_collaboration_shared.py``) and reject with
#  409 if a *different* admin currently holds the lock — so the lock is a
#  real, server-enforced guard against concurrent overwrites, not just a
#  UI hint. There is no lock check on ``builtin.create`` since a
#  not-yet-created resource has no entity id to lock.
# ─────────────────────────────────────────────────────────────────────────────

@builtins_bp.route("/builtin.edit_lock.acquire", methods=["POST"])
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


@builtins_bp.route("/builtin.edit_lock.release", methods=["POST"])
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


@builtins_bp.route("/builtin.edit_lock.heartbeat", methods=["POST"])
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
