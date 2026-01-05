"""
elements/common/validator.py

Validator interface, models, and base class for elements.
Elements define how they validate themselves.

Design:
- Validators return ValidatorReport (what they found)
- Service builds ElementValidationResult (report + metadata)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Mapping

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Validation Data Models
# ─────────────────────────────────────────────────────────────────────────────

class ValidationSeverity(str, Enum):
    """Severity levels for validation messages."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCode(str, Enum):
    """Standard validation codes."""
    # Network errors
    ENDPOINT_UNREACHABLE = "ENDPOINT_UNREACHABLE"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    
    # Dependency errors
    DEPENDENCY_INVALID = "DEPENDENCY_INVALID"
    DEPENDENCY_NOT_FOUND = "DEPENDENCY_NOT_FOUND"
    DEPENDENCY_NOT_VALIDATED = "DEPENDENCY_NOT_VALIDATED"
    
    # Configuration errors
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Status codes
    NO_VALIDATOR = "NO_VALIDATOR"


@dataclass(frozen=True)
class ValidationMessage:
    """A single validation message."""
    severity: ValidationSeverity
    code: str
    message: str
    field: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }


@dataclass
class ValidatorReport:
    """
    What the validator found during validation.
    
    This is the OUTPUT of a validator - pure validation findings.
    Does NOT include element metadata (rid, type) - that's added by the service.
    """
    messages: List[ValidationMessage] = field(default_factory=list)
    checked_dependencies: Dict[str, "ElementValidationResult"] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Valid if no ERROR-severity messages."""
        return not any(m.severity == ValidationSeverity.ERROR for m in self.messages)


@dataclass
class ElementValidationResult:
    """
    Complete validation result for an element.
    
    Built by the service from ValidatorReport + element metadata.
    This is what gets returned to API callers.
    """
    is_valid: bool
    element_rid: str
    element_type: str
    name: Optional[str] = None
    messages: List[ValidationMessage] = field(default_factory=list)
    dependency_results: Dict[str, "ElementValidationResult"] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "element_rid": self.element_rid,
            "element_type": self.element_type,
            "name": self.name,
            "messages": [m.to_dict() for m in self.messages],
            "dependency_results": {
                rid: r.to_dict() for rid, r in self.dependency_results.items()
            },
        }


@dataclass(frozen=True)
class ValidationContext:
    """
    Immutable context passed to validators.
    Contains settings and pre-computed dependency results.
    Pure data only - no functions or service references.
    """
    timeout_seconds: float = 10.0
    dependency_results: Mapping[str, ElementValidationResult] = field(default_factory=dict)

    def get_dependency_result(self, rid: str) -> Optional[ElementValidationResult]:
        """Look up a dependency's validation result."""
        return self.dependency_results.get(rid)

    def with_dependency_results(
        self, 
        results: Dict[str, ElementValidationResult]
    ) -> "ValidationContext":
        """Return a new context with updated dependency results (immutable)."""
        return ValidationContext(
            timeout_seconds=self.timeout_seconds,
            dependency_results=results,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Validator Interface
# ─────────────────────────────────────────────────────────────────────────────

class ElementValidator(ABC):
    """
    Abstract interface for element-specific validators.
    
    Each element type can optionally implement a validator
    by subclassing this and setting validator_cls on its spec.
    
    Validators return ValidatorReport (what they found).
    The service builds ElementValidationResult (report + metadata).
    """

    @abstractmethod
    def validate(
        self,
        config: BaseModel,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate the given config.
        
        Args:
            config: The Pydantic config model to validate
            context: Validation settings and pre-computed dependency results
            
        Returns:
            ValidatorReport with messages and checked dependencies
            
        Note:
            This method must be synchronous. If async operations are needed
            (e.g., network calls), use AsyncBridge internally.
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Base Validator with Utilities
# ─────────────────────────────────────────────────────────────────────────────

class BaseElementValidator(ElementValidator):
    """
    Base class providing common validation utilities.
    
    Subclasses should:
    1. Override validate() to add element-specific checks
    2. Use helper methods like _error(), _warning(), _info()
    3. Call _build_report() to construct the final report
    """

    # ─────────────────────────────────────────────────────────────────────
    # Message helpers
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _error(
        code: str,
        message: str,
        field: Optional[str] = None,
    ) -> ValidationMessage:
        return ValidationMessage(
            severity=ValidationSeverity.ERROR,
            code=code,
            message=message,
            field=field,
        )

    @staticmethod
    def _warning(
        code: str,
        message: str,
        field: Optional[str] = None,
    ) -> ValidationMessage:
        return ValidationMessage(
            severity=ValidationSeverity.WARNING,
            code=code,
            message=message,
            field=field,
        )

    @staticmethod
    def _info(
        code: str,
        message: str,
        field: Optional[str] = None,
    ) -> ValidationMessage:
        return ValidationMessage(
            severity=ValidationSeverity.INFO,
            code=code,
            message=message,
            field=field,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Report builder
    # ─────────────────────────────────────────────────────────────────────
    def _build_report(
        self,
        messages: List[ValidationMessage],
        checked_dependencies: Optional[Dict[str, ElementValidationResult]] = None,
    ) -> ValidatorReport:
        """
        Build a validator report from collected messages.
        
        The service will later combine this with element metadata
        to create the full ElementValidationResult.
        """
        return ValidatorReport(
            messages=messages,
            checked_dependencies=checked_dependencies or {},
        )

    # ─────────────────────────────────────────────────────────────────────
    # Dependency validation helpers
    # ─────────────────────────────────────────────────────────────────────
    def _check_dependency(
        self,
        context: ValidationContext,
        dep_rid: str,
        field_name: str,
        messages: List[ValidationMessage],
        checked_dependencies: Dict[str, ElementValidationResult],
    ) -> bool:
        """
        Check if a dependency is valid.
        
        Returns True if valid or not found (warning only).
        Returns False if dependency is invalid (error added).
        """
        dep_result = context.get_dependency_result(dep_rid)
        
        if dep_result is None:
            # No dep_result = no name available, just use rid
            messages.append(self._warning(
                ValidationCode.DEPENDENCY_NOT_VALIDATED.value,
                f"Dependency '{dep_rid}' was not validated",
                field=field_name,
            ))
            return True  # Not a blocking error
        
        # Add to checked dependencies (regardless of validity)
        checked_dependencies[dep_rid] = dep_result
        
        # Build display name: "Name (rid)" or just "rid"
        display_name = f"'{dep_result.name}' ({dep_rid})" if dep_result.name else f"'{dep_rid}'"
        
        if not dep_result.is_valid:
            messages.append(self._error(
                ValidationCode.DEPENDENCY_INVALID.value,
                f"Dependency {display_name} is invalid",
                field=field_name,
            ))
            return False
        
        return True

