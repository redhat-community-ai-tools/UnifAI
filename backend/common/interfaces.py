from typing import Optional, Dict, Any, TypedDict, Tuple


class ValidationIssue(TypedDict):
    """Structured validation failure returned by validators."""
    issue_key: str
    message: str
    validator_name: str


class DataSourceValidator:
    """Base contract for pre-execution validation with structured errors."""

    # Implementations should override these
    name: str = ""
    error_message: str = ""
    error_message_key: str = ""

    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        """Validate before execution using keyword arguments.

        Return (True, None) if valid, otherwise (False, ValidationIssue).
        """
        ...
    def build_issue(self, message: Optional[str] = None) -> ValidationIssue:
        """Helper for implementations to build a structured ValidationIssue."""
        issue_message = message if message is not None else self.error_message
        return {
            "issue_key": self.error_message_key or "ValidationError",
            "message": issue_message,
            "validator_name": self.name or self.__class__.__name__,
        }
