from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, computed_field
from enum import Enum

from mas.core.identity import Identity


class ShareStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELED = "canceled"


class ShareItemKind(str, Enum):
    RESOURCE = "resource"
    BLUEPRINT = "blueprint"


class ShareInvite(BaseModel):
    """Share invitation with TTL and snapshot for deterministic copying."""
    share_id: str = Field(default_factory=lambda: str(uuid4()))
    sender_identity: Identity
    recipient_identity: Identity
    item_kind: ShareItemKind
    item_id: str
    item_name: str
    message: Optional[str] = None
    status: ShareStatus = ShareStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    
    # TTL configuration (10 days default)
    ttl_days: int = Field(default=10, description="Time to live in days")
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(days=10))
    
    # Full set of identity ids authorised to own the shared item.
    # Populated by the endpoint when the caller shares on behalf of a team so
    # that both the individual user id and the team id are accepted during
    # cloning (dependency traversal also uses this list).  Empty means only
    # sender_identity.id is trusted — preserving legacy behaviour.
    authorized_owner_ids: List[str] = Field(default_factory=list)

    # Result tracking for idempotency
    result_mapping: Dict[str, str] = Field(default_factory=dict)

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if the invitation has expired."""
        return datetime.now(UTC) > self.expires_at

    def __init__(self, **data):
        if 'expires_at' not in data and 'ttl_days' in data:
            data['expires_at'] = datetime.now(UTC) + timedelta(days=data['ttl_days'])
        elif 'expires_at' not in data:
            data['expires_at'] = datetime.now(UTC) + timedelta(days=data.get('ttl_days', 10))
        super().__init__(**data)


class ShareCleanupConfig(BaseModel):
    """Configuration for cleaning up old share invites."""
    # Status-specific cleanup rules
    pending_days: int = Field(default=10, description="Delete pending invites after N days")
    declined_days: int = Field(default=7, description="Delete declined invites after N days")
    canceled_days: int = Field(default=7, description="Delete canceled invites after N days")
    expired_days: int = Field(default=1, description="Delete expired invites after N days")
    
    # Never delete accepted invites (audit trail)
    preserve_accepted: bool = Field(default=True, description="Never delete accepted invites")
    
    # Batch processing
    batch_size: int = Field(default=1000, description="Process cleanup in batches of N records")
    
    # Dry run mode
    dry_run: bool = Field(default=False, description="Count what would be deleted without actually deleting")


class ShareResult(BaseModel):
    """Result of accepting a share invitation."""
    share_id: str
    new_item_id: str
    rid_mapping: Dict[str, str] = Field(default_factory=dict)
    created_resources: int = 0
    name_conflicts: Dict[str, str] = Field(default_factory=dict)


class ShareCleanupResult(BaseModel):
    """Result of a cleanup operation."""
    total_processed: int = 0
    deleted_count: int = 0
    expired_count: int = 0
    pending_count: int = 0
    declined_count: int = 0
    canceled_count: int = 0
    errors: int = 0
    dry_run: bool = False
