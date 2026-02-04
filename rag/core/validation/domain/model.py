"""Validation domain models."""
from typing import TypedDict


class ValidationIssue(TypedDict):
    """Structured validation failure returned by validators."""
    issue_key: str
    message: str
    validator_name: str
