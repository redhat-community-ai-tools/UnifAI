class SessionCancelledException(Exception):
    """Engine-agnostic cancellation signal.

    Each engine adapter translates its native cancel mechanism
    (Temporal CancelledError, Celery SoftTimeLimitExceeded, etc.)
    into this exception inside its ops methods.
    The BackgroundSessionRunner catches it and calls ops.cancel().
    """
    pass


class SessionAlreadyCancelledError(Exception):
    """Raised when a session is already in CANCELLED state at begin() time."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' is already cancelled")


class SessionBlueprintError(Exception):
    """Base class for session blueprint-related errors."""
    pass


class BlueprintNotFoundError(SessionBlueprintError):
    """Raised when a blueprint required by a session is not found or has been deleted."""
    
    def __init__(self, blueprint_id: str, session_id: str = None):
        self.blueprint_id = blueprint_id
        self.session_id = session_id
        
        if session_id:
            msg = f"Cannot load session '{session_id}': Blueprint '{blueprint_id}' has been deleted"
        else:
            msg = f"Blueprint '{blueprint_id}' does not exist or has been deleted"
            
        super().__init__(msg)
