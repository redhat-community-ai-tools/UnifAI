"""
Custom exceptions for Blueprint operations.
Provides specific error types for better debugging and error handling.
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_VALID_METADATA_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


class BlueprintError(Exception):
    """Base exception for all blueprint-related errors."""
    pass


class BlueprintNotFoundError(BlueprintError):
    """Raised when a blueprint cannot be found by ID."""
    def __init__(self, blueprint_id: str, message: str = None):
        self.blueprint_id = blueprint_id
        self.message = message or f"Blueprint '{blueprint_id}' not found"
        super().__init__(self.message)
        

class BlueprintAccessDeniedError(BlueprintError):
    """Raised when a user doesn't have access to a blueprint."""
    def __init__(self, blueprint_id: str, user_id: str, message: str = None):
        self.blueprint_id = blueprint_id
        self.user_id = user_id
        self.message = message or f"User '{user_id}' does not have access to blueprint '{blueprint_id}'"
        super().__init__(self.message)


class BlueprintSaveError(BlueprintError):
    """Raised when saving a blueprint fails."""
    def __init__(self, message: str, cause: Exception = None):
        self.message = message
        self.cause = cause
        super().__init__(self.message)


class BlueprintMetadataError(BlueprintError):
    """Raised when updating blueprint metadata fails."""
    def __init__(self, blueprint_id: str, message: str = None):
        self.blueprint_id = blueprint_id
        self.message = message or f"Failed to update metadata for blueprint '{blueprint_id}'"
        super().__init__(self.message)


class InvalidMetadataKeysError(BlueprintError):
    """Raised when metadata keys contain characters unsafe for storage (e.g. '.' or '$')."""
    def __init__(self, bad_keys: List[str]):
        self.bad_keys = bad_keys
        super().__init__(f"Invalid metadata key(s): {bad_keys}")


def validate_metadata_keys(metadata: Dict[str, Any]) -> None:
    """Reject metadata keys that would corrupt Mongo dot-notation paths or clash with operators."""
    bad = [k for k in metadata if not _VALID_METADATA_KEY.match(k)]
    if bad:
        logger.info("Rejected metadata keys: %s", bad)
        raise InvalidMetadataKeysError(bad)


class PromptShortcutsValidationError(BlueprintError):
    """Raised when prompt shortcuts fail validation (bad text, duplicate ids, >3 manual items)."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

