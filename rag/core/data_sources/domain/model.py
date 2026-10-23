"""DataSource domain model."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class DataSource:
    """Domain model for a data source."""
    source_id: str
    source_name: str
    source_type: str
    pipeline_id: str
    upload_by: str
    created_at: datetime
    last_sync_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    type_data: Dict[str, Any] = field(default_factory=dict)
    # "private" (owner only), "shared" (owner + members of acl_groups, see AccessScope) or "public" (every caller)
    visibility: str = "private"
    acl_groups: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataSource":
        """Create a DataSource instance from a dictionary."""
        return cls(
            source_id=data.get("source_id", ""),
            source_name=data.get("source_name", ""),
            source_type=data.get("source_type", ""),
            pipeline_id=data.get("pipeline_id", ""),
            upload_by=data.get("upload_by", ""),
            created_at=data.get("created_at", datetime.now()),
            last_sync_at=data.get("last_sync_at"),
            tags=data.get("tags", []),
            type_data=data.get("type_data", {}),
            visibility=data.get("visibility", "private"),
            acl_groups=list(data.get("acl_groups", []) or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the DataSource instance to a dictionary."""
        return asdict(self)

