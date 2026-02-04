"""TermsApproval domain model."""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class TermsApproval:
    """Domain model for user terms approval."""
    username: str
    approved_at: datetime
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TermsApproval":
        """Create a TermsApproval instance from a dictionary."""
        return cls(
            username=data.get("username", ""),
            approved_at=data.get("approved_at", datetime.utcnow()),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the TermsApproval instance to a dictionary."""
        return asdict(self)
