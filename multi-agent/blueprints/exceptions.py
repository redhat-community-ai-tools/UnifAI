"""
Custom exceptions for Blueprint operations.
Provides specific error types for better debugging and error handling.
"""


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

