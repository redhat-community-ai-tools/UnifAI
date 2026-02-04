"""Terms approval application service."""
from typing import Dict, Any

from core.user.terms_approval.domain.repository import TermsApprovalRepository
from shared.logger import logger


class TermsApprovalService:
    """Application service for AI transparency terms approval operations."""

    def __init__(self, approval_repo: TermsApprovalRepository):
        self._repo = approval_repo

    def check_approval_status(self, username: str) -> Dict[str, Any]:
        """
        Check if a user has approved the AI transparency notice.
        
        Returns:
            Dictionary with approval status and username
        """
        is_approved = self._repo.is_user_approved(username)
        return {
            "approved": is_approved,
            "username": username
        }

    def record_approval(self, username: str) -> Dict[str, Any]:
        """
        Record a user's approval of the AI transparency notice.
        
        Returns:
            Dictionary with user information indicating successful recording
        """
        approval = self._repo.record_approval(username)
        logger.info(f"Recorded terms approval for user: {username}")
        return {
            "username": approval.username,
            "approved": True
        }
