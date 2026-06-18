"""Flask inbound adapter — Blueprint REST endpoints.

All routes follow the existing ``blueprint.*.verb`` naming convention
used throughout the MAS API.  Version-history endpoints were added in
GENIE-1336.

Response envelope
-----------------
Success: ``{"success": true, "data": <payload>}``
Error:   ``{"success": false, "error": "<message>"}``

Exception-to-HTTP mapping (adapter-layer concern)
--------------------------------------------------
This adapter is the **sole** location where domain exceptions are mapped
to HTTP status codes.  The domain layer (``mas.blueprints.exceptions``)
is transport-agnostic and contains no HTTP references.

  BlueprintNotFoundError      → 404
  VersionNotFoundError        → 404
  BlueprintAccessDeniedError  → 403
  ConcurrentModificationError → 409
  FeatureNotConfiguredError → 501
  BlueprintError (other)      → 500
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, request
from mas.blueprints.exceptions import (
    BlueprintAccessDeniedError,
    BlueprintError,
    BlueprintNotFoundError,
    ConcurrentModificationError,
    FeatureNotConfiguredError,
    VersionNotFoundError,
)
from mas.core.identity.models import Identity
from werkzeug.exceptions import HTTPException

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask Blueprint registration
# ---------------------------------------------------------------------------

bp = Blueprint("blueprints", __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(data: Any, status: int = 200) -> tuple[Any, int]:
    """Return a standardised success JSON envelope."""
    return jsonify({"success": True, "data": data}), status


def _err(message: str, status: int = 500) -> tuple[Any, int]:
    """Return a standardised error JSON envelope."""
    return jsonify({"success": False, "error": message}), status


def _parse_int_param(
    value: str | None,
    default: int,
    param_name: str,
    *,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    """
    Safely parse a string to an integer with clamping and error handling.

    Parameters
    ----------
    value:
        Raw string from the request (may be ``None``).
    default:
        Returned when *value* is ``None``.
    param_name:
        Used in the 400 error message when parsing fails.
    min_val / max_val:
        If provided, the parsed value is clamped to this range.

    Raises
    ------
    werkzeug.exceptions.HTTPException (400)
        If *value* is not a valid integer.
    """
    if value is None:
        result = default
    else:
        try:
            result = int(value)
        except (ValueError, TypeError):
            abort(400, f"Invalid value for {param_name!r}: must be an integer")
    if min_val is not None:
        result = max(min_val, result)
    if max_val is not None:
        result = min(max_val, result)
    return result


def _require_auth() -> Identity:
    """
    Extract and validate caller identity from the request.

    Looks for an ``X-Identity-Type`` / ``X-Identity-Id`` header pair.
    Returns the validated ``Identity`` on success, or aborts with 401.
    """
    identity_type = request.headers.get("X-Identity-Type")
    identity_id = request.headers.get("X-Identity-Id")

    if not identity_type or not identity_id:
        abort(
            401,
            "Missing authentication headers: "
            "X-Identity-Type and X-Identity-Id are required",
        )

    return Identity(type=identity_type, id=identity_id)


def _handle_blueprint_errors(fn: Callable) -> Callable:
    """
    Decorator that converts domain exceptions to HTTP responses.

    Order matters: subclasses must be caught before their base classes.

    **Security**: unhandled exceptions are logged server-side and the
    response body contains a generic message — raw exception text is
    never leaked to the client.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except VersionNotFoundError as exc:
            return _err(str(exc), 404)
        except BlueprintNotFoundError as exc:
            return _err(str(exc), 404)
        except BlueprintAccessDeniedError as exc:
            return _err(str(exc), 403)
        except ConcurrentModificationError as exc:
            return _err(str(exc), 409)
        except FeatureNotConfiguredError as exc:
            # Feature-not-configured is surfaced as 501.
            return _err(str(exc), 501)
        except BlueprintError as exc:
            # All specific domain exceptions are handled above; any
            # remaining BlueprintError subclass maps to 500.
            return _err(str(exc), 500)
        except HTTPException as exc:
            # Convert Werkzeug HTTP exceptions (e.g. abort(400)) into our
            # standard JSON error envelope so all responses are consistent.
            description = exc.description or exc.name or "HTTP error"
            return _err(str(description), exc.code or 500)
        except Exception:  # noqa: BLE001
            # Log the full traceback server-side but return a sanitised
            # message to the client to avoid leaking implementation details.
            _logger.exception("Unhandled error in blueprint endpoint")
            return _err("Internal server error", 500)

    return wrapper


def _get_json_body() -> dict:
    """Return the parsed JSON request body or abort with 400."""
    data = request.get_json(silent=True)
    if data is None:
        abort(
            400,
            "Request body must be valid JSON with Content-Type: application/json",
        )
    return data


def _require_body_keys(body: dict, *keys: str) -> None:
    """
    Validate that all *keys* are present in *body*.

    Aborts with 400 and a descriptive message if any required key is missing.
    """
    missing = [k for k in keys if k not in body]
    if missing:
        abort(400, f"Missing required field(s): {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Blueprint CRUD endpoints
# ---------------------------------------------------------------------------


@bp.route("/blueprint.save", methods=["POST"])
@_handle_blueprint_errors
def blueprint_save():
    """
    POST /blueprint.save

    Body: {
        "identity": {"type": "user"|"team", "id": "<id>"},
        "spec_dict": {...},
        "metadata": {...}   # optional
    }
    """
    _require_auth()
    body = _get_json_body()
    _require_body_keys(body, "identity", "spec_dict")
    identity = Identity.model_validate(body["identity"])
    spec_dict = body["spec_dict"]
    metadata = body.get("metadata", {})

    svc = current_app.container.blueprint_service
    blueprint_id = svc.create_blueprint(
        identity=identity, spec_dict=spec_dict, metadata=metadata
    )
    return _ok({"blueprint_id": blueprint_id}, 201)


@bp.route("/blueprint.update", methods=["PUT"])
@_handle_blueprint_errors
def blueprint_update():
    """
    PUT /blueprint.update

    Body: {
        "blueprint_id": "<id>",
        "spec_dict": {...},
        "change_summary": "..."  # optional
        "user_id": "..."         # optional
    }
    """
    _require_auth()
    body = _get_json_body()
    _require_body_keys(body, "blueprint_id", "spec_dict")
    blueprint_id = body["blueprint_id"]
    spec_dict = body["spec_dict"]
    change_summary = body.get("change_summary")
    user_id = body.get("user_id", "")

    svc = current_app.container.blueprint_service
    svc.update_draft(
        blueprint_id=blueprint_id,
        draft_dict=spec_dict,
        user_id=user_id,
        change_summary=change_summary,
    )
    return _ok({"blueprint_id": blueprint_id})


@bp.route("/blueprint.info.get", methods=["GET"])
@_handle_blueprint_errors
def blueprint_info_get():
    """
    GET /blueprint.info.get?blueprint_id=<id>
    """
    _require_auth()
    blueprint_id = request.args.get("blueprint_id")
    if not blueprint_id:
        return _err("Missing required query parameter: blueprint_id", 400)

    svc = current_app.container.blueprint_service
    doc = svc.load_blueprint(blueprint_id)
    return _ok(doc.model_dump())


@bp.route("/remove.blueprint", methods=["DELETE"])
@_handle_blueprint_errors
def remove_blueprint():
    """
    DELETE /remove.blueprint?blueprint_id=<id>
    """
    _require_auth()
    blueprint_id = request.args.get("blueprint_id")
    if not blueprint_id:
        return _err("Missing required query parameter: blueprint_id", 400)

    svc = current_app.container.blueprint_service
    deleted = svc.delete_blueprint(blueprint_id)
    if not deleted:
        return _err(f"Blueprint not found: {blueprint_id!r}", 404)
    return _ok({"deleted": True})


@bp.route("/available.blueprints.summary.get", methods=["GET"])
@_handle_blueprint_errors
def available_blueprints_summary_get():
    """
    GET /available.blueprints.summary.get
    ?identity_type=user&identity_id=alice&skip=0&limit=20
    """
    _require_auth()
    identity_type = request.args.get("identity_type")
    identity_id = request.args.get("identity_id")
    skip = _parse_int_param(request.args.get("skip"), 0, "skip", min_val=0)
    limit = _parse_int_param(request.args.get("limit"), 20, "limit", min_val=1, max_val=100)

    identity = None
    if identity_type and identity_id:
        identity = Identity(type=identity_type, id=identity_id)

    svc = current_app.container.blueprint_service
    docs = svc.list_blueprints(identity=identity, skip=skip, limit=limit)
    total = svc.count_blueprints(identity=identity)

    return _ok(
        {
            "items": [d.model_dump() for d in docs],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    )


# ---------------------------------------------------------------------------
# Version-history endpoints  (GENIE-1336)
# ---------------------------------------------------------------------------


@bp.route("/blueprint.versions.list", methods=["GET"])
@_handle_blueprint_errors
def blueprint_versions_list():
    """
    GET /blueprint.versions.list
    ?blueprint_id=<id>&page=1&page_size=20

    Returns a paginated list of version summaries sorted newest-first.
    ``spec_dict_snapshot`` is intentionally excluded from the list response
    for payload efficiency — use ``/blueprint.version.get`` to fetch it.

    Errors
    ------
    400 — missing blueprint_id
    404 — blueprint not found
    501 — versioning feature not configured on the server
    """
    _require_auth()
    blueprint_id = request.args.get("blueprint_id")
    if not blueprint_id:
        return _err("Missing required query parameter: blueprint_id", 400)

    page = _parse_int_param(request.args.get("page"), 1, "page", min_val=1)
    page_size = _parse_int_param(
        request.args.get("page_size"), 20, "page_size", min_val=1, max_val=100
    )

    svc = current_app.container.blueprint_service
    result = svc.list_versions(
        blueprint_id=blueprint_id,
        page=page,
        page_size=page_size,
    )
    return _ok(result)


@bp.route("/blueprint.version.get", methods=["GET"])
@_handle_blueprint_errors
def blueprint_version_get():
    """
    GET /blueprint.version.get?blueprint_id=<id>&version=<n>

    Returns the full version detail including ``spec_dict_snapshot``.

    Errors
    ------
    400 — missing or invalid query parameters
    404 — blueprint or version not found
    501 — versioning feature not configured on the server
    """
    _require_auth()
    blueprint_id = request.args.get("blueprint_id")
    version_str = request.args.get("version")

    if not blueprint_id:
        return _err("Missing required query parameter: blueprint_id", 400)
    if not version_str:
        return _err("Missing required query parameter: version", 400)

    try:
        version = int(version_str)
    except ValueError:
        return _err(f"Invalid version: {version_str!r} must be an integer", 400)

    svc = current_app.container.blueprint_service
    detail = svc.load_version(blueprint_id=blueprint_id, version_number=version)
    return _ok(detail)


@bp.route("/blueprint.version.restore", methods=["POST"])
@_handle_blueprint_errors
def blueprint_version_restore():
    """
    POST /blueprint.version.restore

    Body: {"blueprint_id": "<id>", "version": <n>, "user_id": "..."}

    Restores the blueprint's live spec to the snapshot captured at
    ``version``.  The current state is saved as a new snapshot before the
    restore so no history is lost.

    Errors
    ------
    400 — missing or invalid body fields
    404 — blueprint or version not found
    409 — concurrent modification conflict (re-fetch and retry)
    501 — versioning feature not configured on the server
    """
    identity = _require_auth()
    body = _get_json_body()

    blueprint_id = body.get("blueprint_id")
    target_version = body.get("version")
    user_id = body.get("user_id", identity.id)

    if not blueprint_id:
        return _err("Missing required field: blueprint_id", 400)
    if target_version is None:
        return _err("Missing required field: version", 400)
    if isinstance(target_version, bool) or not isinstance(target_version, int) or target_version < 1:
        return _err(
            f"Invalid version: {target_version!r} must be a positive integer", 400
        )

    svc = current_app.container.blueprint_service
    svc.restore_version(
        blueprint_id=blueprint_id,
        target_version=target_version,
        user_id=user_id,
    )

    return _ok(
        {
            "blueprint_id": blueprint_id,
            "restored_from_version": target_version,
            "message": f"Blueprint restored to version {target_version}.",
        }
    )


# ---------------------------------------------------------------------------
# Alias required by integration tests
# ---------------------------------------------------------------------------

blueprints_bp = bp
