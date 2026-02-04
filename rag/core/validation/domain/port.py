"""Validation port - abstract interface for validators."""
from abc import ABC, abstractmethod
from typing import Optional, Any, Tuple

from core.validation.domain.model import ValidationIssue


class DataSourceValidator(ABC):
    """Base contract for pre-execution validation with structured errors."""

    # Implementations should override these
    name: str = ""
    error_message: str = ""
    error_message_key: str = ""

    @abstractmethod
    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        """Validate before execution using keyword arguments.

        Return (True, None) if valid, otherwise (False, ValidationIssue).
        """
        pass

    def build_issue(self, message: Optional[str] = None) -> ValidationIssue:
        """Helper for implementations to build a structured ValidationIssue."""
        issue_message = message if message is not None else self.error_message
        return {
            "issue_key": self.error_message_key or "ValidationError",
            "message": issue_message,
            "validator_name": self.name or self.__class__.__name__,
        }
