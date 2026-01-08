from typing import Optional, Dict, Any
from pymongo.collection import Collection
from datetime import datetime
from shared.logger import logger

class TermsUserApprovalRepository:
    """Repository for managing AI transparency user approvals in MongoDB."""
    
    def __init__(self, col: Collection):
        self.col = col

    def is_user_approved(self, username: str) -> bool:
        """Check if a user has approved the AI transparency notice."""
        try:
            doc = self.col.find_one({"username": username})
            return doc is not None
        except Exception as e:
            logger.error(f"Error checking user approval for {username}: {e}")
            return False

    def record_user_approval(self, username: str) -> Dict[str, Any]:
        """Record a user's approval by creating their approval document."""
        try:
            now = datetime.utcnow()
            result = self.col.update_one(
                {"username": username},
                {
                    "$set": {"approved_at": now},
                    "$setOnInsert": {"username": username, "created_at": now}
                },
                upsert=True
            )
            return {
                "success": True,
                "username": username,
                "approved": True
            }
        except Exception as e:
            logger.error(f"Error recording user approval for {username}: {e}")
            return {"success": False, "error": str(e)}

    def get_user_approval(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user approval record."""
        try:
            doc = self.col.find_one({"username": username}, {"_id": 0})
            return doc
        except Exception as e:
            logger.error(f"Error getting user approval for {username}: {e}")
            return None

