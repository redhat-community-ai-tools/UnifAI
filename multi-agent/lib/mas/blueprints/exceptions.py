"""
Domain exception hierarchy for the Blueprint bounded context.

All exceptions inherit from ``BlueprintError`` so callers can catch either
a specific subclass or the entire domain-error surface in one clause.

HTTP status codes are annotated as class attributes for the Flask adapter
layer — the domain itself does not import Flask.

GENIE-1336: Added ``VersionNotFoundError`` and ``ConcurrentModificationError``.
"""

from __future__ import annotations


class BlueprintError(Exception):
    """Base class for all blueprint domain exceptions."""

    http_status: int = 500


# ---------------------------------------------------------------------------
# 404 – Not Found
# ---------------------------------------------------------------------------


class BlueprintNotFoundError(BlueprintError):
    """Raised when a blueprint cannot be located by its ID."""

    http_status = 404

    def __init__(self, blueprint_id: str) -> None:
        self.blueprint_id = blueprint_id
        super().__init__(f"Blueprint not found: {blueprint_id!r}")


class VersionNotFoundError(BlueprintError):
    """Raised when a specific version snapshot does not exist."""

    http_status = 404

    def __init__(self, blueprint_id: str, version: int) -> None:
        self.blueprint_id = blueprint_id
        self.version = version
        super().__init__(
            f"Version {version} of blueprint {blueprint_id!r} not found"
        )


# ---------------------------------------------------------------------------
# 403 – Access Denied
# ---------------------------------------------------------------------------


class BlueprintAccessDeniedError(BlueprintError):
    """Raised when the caller lacks permission to operate on a blueprint."""

    http_status = 403

    def __init__(self, blueprint_id: str, reason: str = "") -> None:
        self.blueprint_id = blueprint_id
        msg = f"Access denied for blueprint {blueprint_id!r}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# 409 – Conflict
# ---------------------------------------------------------------------------


class ConcurrentModificationError(BlueprintError):
    """
    Raised when an OCC write is rejected because the document was modified
    by another writer between the read and the write.

    The client should re-fetch the latest version and retry.
    """

    http_status = 409

    def __init__(self, blueprint_id: str, expected_version: int) -> None:
        self.blueprint_id = blueprint_id
        self.expected_version = expected_version
        super().__init__(
            f"Concurrent modification conflict for blueprint {blueprint_id!r}: "
            f"expected version {expected_version} but the document was already "
            f"updated by another writer. Re-fetch and retry."
        )


# ---------------------------------------------------------------------------
# 500 – Internal / Save Errors
# ---------------------------------------------------------------------------


class BlueprintSaveError(BlueprintError):
    """Raised when the repository fails to persist a blueprint."""

    http_status = 500

    def __init__(self, blueprint_id: str, cause: str = "") -> None:
        self.blueprint_id = blueprint_id
        msg = f"Failed to save blueprint {blueprint_id!r}"
        if cause:
            msg += f": {cause}"
        super().__init__(msg)


class BlueprintMetadataError(BlueprintError):
    """Raised when blueprint metadata is invalid or cannot be updated."""

    http_status = 500

    def __init__(self, blueprint_id: str, cause: str = "") -> None:
        self.blueprint_id = blueprint_id
        msg = f"Metadata error for blueprint {blueprint_id!r}"
        if cause:
            msg += f": {cause}"
        super().__init__(msg)
