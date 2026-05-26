from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from ..models import ShareInvite, ShareStatus, ShareCleanupConfig, ShareCleanupResult
from mas.core.identity import Identity


class ShareRepository(ABC):
    @abstractmethod
    def save(self, invite: ShareInvite) -> str:
        """Save share invite."""
        pass

    @abstractmethod
    def get(self, share_id: str) -> ShareInvite:
        """Get share invite by ID."""
        pass

    @abstractmethod
    def update_status(self, share_id: str, status: ShareStatus, 
                     result_mapping: Optional[dict] = None) -> bool:
        """Update invite status."""
        pass

    @abstractmethod
    def list_for_recipient(self, recipient: Identity, 
                          status: Optional[ShareStatus] = None,
                          skip: int = 0, limit: int = 100) -> List[ShareInvite]:
        """List invites for recipient, scoped by identity type and id."""
        pass

    @abstractmethod
    def list_for_sender(self, sender: Identity,
                       status: Optional[ShareStatus] = None,
                       skip: int = 0, limit: int = 100) -> List[ShareInvite]:
        """List invites sent by identity, scoped by identity type and id."""
        pass

    @abstractmethod
    def exists(self, share_id: str) -> bool:
        """Check if invite exists."""
        pass

    @abstractmethod
    def delete(self, share_id: str) -> bool:
        """Delete a share invite. Returns True if deleted."""
        pass

    @abstractmethod
    def cleanup_old_invites(self, config: ShareCleanupConfig) -> ShareCleanupResult:
        """Delete old invites based on configuration. Returns cleanup result."""
        pass
    
    @abstractmethod
    def cleanup_expired_invites(self, *, dry_run: bool = False, batch_size: int = 1000) -> ShareCleanupResult:
        """Delete expired invites based on TTL. Returns cleanup result."""
        pass
    
    @abstractmethod
    def count_by_status_and_age(self, *, older_than: datetime, status: Optional[ShareStatus] = None) -> int:
        """Count invites by status and age for cleanup planning."""
        pass
