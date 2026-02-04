"""MongoDB adapter for TermsApprovalRepository port."""
from typing import Optional
from datetime import datetime

from pymongo.collection import Collection

from core.user.terms_approval.domain.model import TermsApproval
from core.user.terms_approval.domain.repository import TermsApprovalRepository
from shared.logger import logger


class MongoTermsApprovalRepository(TermsApprovalRepository):
    """MongoDB implementation of the TermsApprovalRepository port."""

    def __init__(self, collection: Collection):
        self._col = collection
        self._col.create_index("username", unique=True)

    def is_user_approved(self, username: str) -> bool:
        """Check if a user has approved the AI transparency notice."""
        try:
            doc = self._col.find_one({"username": username})
            return doc is not None
        except Exception as e:
            logger.error(f"Error checking user approval for {username}: {e}")
            return False

    def record_approval(self, username: str) -> TermsApproval:
        """Record a user's approval by creating/updating their approval document."""
        now = datetime.utcnow()
        self._col.update_one(
            {"username": username},
            {
                "$set": {"approved_at": now},
                "$setOnInsert": {"username": username, "created_at": now}
            },
            upsert=True,
        )
        return TermsApproval(username=username, approved_at=now, created_at=now)

    def find_by_username(self, username: str) -> Optional[TermsApproval]:
        """Get user approval record by username."""
        try:
            doc = self._col.find_one({"username": username}, {"_id": 0})
            return TermsApproval.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error getting user approval for {username}: {e}")
            return None
