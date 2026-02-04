"""Registration port - abstract interface for registration use cases."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

from core.registration.domain.model import BaseSourceData


class RegistrationPort(ABC):
    """
    Abstract base for source registration flows.

    Implementations should orchestrate validation and persistence while preserving
    the existing behavior for their specific source type.
    
    Supports skip_validation flag:
    - When False (default): Full validation is performed (for external API calls)
    - When True: Skip pre-upload validations, only perform content-based validation
      like MD5 duplicate checking (for UI calls that pre-validated via /docs/validate)
    """

    # Subclasses must define this
    DATA_SOURCE_TYPE: str = ""

    @property
    @abstractmethod
    def source_data(self) -> BaseSourceData:
        """Aggregated, immutable source data object (id, name, pipeline_id, form_data, etc.)."""
        ...

    @abstractmethod
    def run_validator(self) -> Tuple[bool, Dict[str, Any] | None]:
        """Run source-specific validation for a single instance and return (is_valid, issue)."""
        ...

    @abstractmethod
    def register(self) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """
        Register a single instance. Returns (registered_source_dict, issue_dict).
        If registration is successful, issue_dict should be None. If validation fails,
        registered_source_dict should be None and issue_dict should contain structured info.
        """
        ...

    def run_registration(self) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """
        Orchestrate the single-item registration flow:
        1) validate the instance
        2) register (persist) if valid
        Returns (registered_source_dict, issue_dict)
        """
        is_valid, issue = self.run_validator()
        if not is_valid:
            return None, issue
        return self.register()
