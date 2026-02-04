"""MD5 Duplicate Validator - checks for content duplicates."""
from typing import Optional, Any, Tuple, Protocol
from shared.logger import logger

from core.validation.domain.port import DataSourceValidator
from core.validation.domain.model import ValidationIssue


class DuplicateCheckerPort(Protocol):
    """Port for duplicate checking - implementations injected at runtime."""
    def is_duplicate(self, doc: dict) -> bool:
        ...


class DuplicateValidator(DataSourceValidator):
    """Validates that the file content (MD5) is not a duplicate."""
    
    name = "DuplicateValidator"
    error_message = "This file appears to be a duplicate of an existing successfully processed file and was not added. File: {source_name}"
    error_message_key = "File duplicated error"

    def __init__(self, duplicate_checker: DuplicateCheckerPort) -> None:
        self._duplicate_checker = duplicate_checker

    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        try:
            if self._duplicate_checker.is_duplicate(kwargs):
                return False, self.build_issue(
                    self.error_message.format(source_name=kwargs.get("source_name"))
                )
        except Exception as e:
            logger.warning(
                f"Duplicate check failed for {kwargs.get('source_name')}, "
                f"allowing upload: {e}"
            )
            return True, None

        return True, None
