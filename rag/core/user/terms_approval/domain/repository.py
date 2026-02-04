"""TermsApproval repository port (interface)."""
from abc import ABC, abstractmethod
from typing import Optional

from core.user.terms_approval.domain.model import TermsApproval


class TermsApprovalRepository(ABC):
    """Port for TermsApproval persistence."""

    @abstractmethod
    def is_user_approved(self, username: str) -> bool:
        """Check if a user has approved the AI transparency notice."""
        ...

    @abstractmethod
    def record_approval(self, username: str) -> TermsApproval:
        """Record a user's approval. Returns the created/updated approval."""
        ...

    @abstractmethod
    def find_by_username(self, username: str) -> Optional[TermsApproval]:
        """Get user approval record by username."""
        ...
