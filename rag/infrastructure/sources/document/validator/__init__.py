"""Document validation adapters."""
from infrastructure.sources.document.validator.duplicate_checker import DocumentDuplicateCheckerAdapter
from infrastructure.sources.document.validator.name_duplicate_checker import NameDuplicateCheckerAdapter

__all__ = ["DocumentDuplicateCheckerAdapter", "NameDuplicateCheckerAdapter"]
