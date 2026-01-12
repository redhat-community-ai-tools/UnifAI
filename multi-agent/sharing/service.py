from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .models import ShareInvite, ShareResult, ShareStatus, ShareItemKind, ShareCleanupConfig, ShareCleanupResult
from .repository.base import ShareRepository
from .cloner import ShareCloner


class ShareService:
    """
    Service layer for sharing functionality.
    Follows existing service patterns.
    """
    
    def __init__(self, 
                 share_repository: ShareRepository,
                 cloner: ShareCloner):
        self._repo = share_repository
        self._cloner = cloner

    def create_invite(self, *, sender_user_id: str, recipient_user_id: str,
                     item_kind: ShareItemKind, item_id: str,
                     message: Optional[str] = None, ttl_days: int = 10) -> str:
        """Create share invitation."""
        # Validate item exists and is owned by sender
        item_name = self._validate_and_get_name(item_kind, item_id, sender_user_id)
        
        invite = ShareInvite(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            item_kind=item_kind,
            item_id=item_id,
            item_name=item_name,
            message=message,
            ttl_days=ttl_days
        )
        
        return self._repo.save(invite)

    def accept_invite(self, share_id: str, *, recipient_user_id: str) -> ShareResult:
        """Accept invitation and perform cloning."""
        invite = self._repo.get(share_id)
        
        # Validate recipient
        if invite.recipient_user_id != recipient_user_id:
            raise ValueError("Not authorized to accept this invite")
        
        # Check if expired
        if invite.is_expired:
            raise ValueError("Invitation has expired")
        
        # Check idempotency
        if invite.status == ShareStatus.ACCEPTED and invite.result_mapping:
            return self._build_result_from_mapping(invite)
        
        if invite.status != ShareStatus.PENDING:
            raise ValueError(f"Invite is not pending (status: {invite.status})")

        # Perform cloning
        try:
            if invite.item_kind == ShareItemKind.RESOURCE:
                rid_mapping, name_conflicts = self._cloner.clone_resource_graph(
                    root_rid=invite.item_id,
                    sender_user_id=invite.sender_user_id,
                    recipient_user_id=recipient_user_id
                )
                new_item_id = rid_mapping[invite.item_id]
                result_mapping = rid_mapping
                
            elif invite.item_kind == ShareItemKind.BLUEPRINT:
                new_blueprint_id, rid_mapping, name_conflicts = self._cloner.clone_blueprint(
                    blueprint_id=invite.item_id,
                    sender_user_id=invite.sender_user_id,
                    recipient_user_id=recipient_user_id
                )
                new_item_id = new_blueprint_id
                result_mapping = {**rid_mapping, "blueprint_id": new_blueprint_id}
            
            # Update status
            self._repo.update_status(share_id, ShareStatus.ACCEPTED, result_mapping)
            
            return ShareResult(
                share_id=share_id,
                new_item_id=new_item_id,
                rid_mapping=rid_mapping,
                created_resources=len(rid_mapping),
                name_conflicts=name_conflicts
            )
            
        except Exception as e:
            raise ValueError(f"Failed to accept share: {str(e)}")

    def decline_invite(self, share_id: str, *, recipient_user_id: str) -> None:
        """Decline invitation."""
        invite = self._repo.get(share_id)
        
        if invite.recipient_user_id != recipient_user_id:
            raise ValueError("Not authorized to decline this invite")
        
        if invite.status != ShareStatus.PENDING:
            raise ValueError(f"Invite is not pending (status: {invite.status})")
        
        self._repo.update_status(share_id, ShareStatus.DECLINED)

    def cancel_invite(self, share_id: str, *, sender_user_id: str) -> None:
        """Cancel sent invitation."""
        invite = self._repo.get(share_id)
        
        if invite.sender_user_id != sender_user_id:
            raise ValueError("Not authorized to cancel this invite")
        
        if invite.status != ShareStatus.PENDING:
            raise ValueError(f"Cannot cancel invite with status: {invite.status}")
        
        self._repo.update_status(share_id, ShareStatus.CANCELED)

    def list_received_invites(self, recipient_user_id: str, 
                             status: Optional[ShareStatus] = None,
                             skip: int = 0, limit: int = 100) -> List[ShareInvite]:
        """List received invitations."""
        return self._repo.list_for_recipient(recipient_user_id, status, skip, limit)

    def list_sent_invites(self, sender_user_id: str,
                         status: Optional[ShareStatus] = None,
                         skip: int = 0, limit: int = 100) -> List[ShareInvite]:
        """List sent invitations."""
        return self._repo.list_for_sender(sender_user_id, status, skip, limit)

    def get_invite(self, share_id: str) -> ShareInvite:
        """Get invitation details."""
        return self._repo.get(share_id)

    def _validate_and_get_name(self, item_kind: ShareItemKind, 
                              item_id: str, sender_user_id: str) -> str:
        """Validate item ownership and get name."""
        if item_kind == ShareItemKind.RESOURCE:
            resource = self._cloner.resources.get(item_id)
            if resource.user_id != sender_user_id:
                raise ValueError(f"Resource {item_id} not owned by sender")
            return resource.name
            
        elif item_kind == ShareItemKind.BLUEPRINT:
            bp_doc = self._cloner.blueprints.get_blueprint_draft_doc(item_id)
            if bp_doc["user_id"] != sender_user_id:
                raise ValueError(f"Blueprint {item_id} not owned by sender")
            return bp_doc["spec_dict"]["name"]
        
        raise ValueError(f"Unknown item kind: {item_kind}")

    def _build_result_from_mapping(self, invite: ShareInvite) -> ShareResult:
        """Build result from existing mapping (for idempotency)."""
        if invite.item_kind == ShareItemKind.RESOURCE:
            new_item_id = invite.result_mapping.get(invite.item_id, "")
            rid_mapping = invite.result_mapping
        else:  # BLUEPRINT
            new_item_id = invite.result_mapping.get("blueprint_id", "")
            rid_mapping = {k: v for k, v in invite.result_mapping.items() 
                          if k != "blueprint_id"}
        
        return ShareResult(
            share_id=invite.share_id,
            new_item_id=new_item_id,
            rid_mapping=rid_mapping
        )

    def delete_invite(self, share_id: str, *, user_id: str) -> None:
        """Delete share invitation with authorization."""
        invite = self._repo.get(share_id)
        
        # Check authorization
        if not self._can_delete_invite(invite, user_id):
            raise ValueError("Not authorized to delete this invite")
        
        # Don't allow deleting ACCEPTED invites (audit trail)
        if invite.status == ShareStatus.ACCEPTED:
            raise ValueError("Cannot delete accepted invites")
        
        if not self._repo.delete(share_id):
            raise ValueError("Failed to delete invite")

    def cleanup_old_invites(self, config: Optional[ShareCleanupConfig] = None) -> ShareCleanupResult:
        """Cleanup old invites based on configuration."""
        if config is None:
            config = ShareCleanupConfig()  # Use defaults
        
        return self._repo.cleanup_old_invites(config)

    def cleanup_expired_invites(self, *, dry_run: bool = False) -> ShareCleanupResult:
        """Cleanup expired invites based on TTL."""
        return self._repo.cleanup_expired_invites(dry_run=dry_run)

    def get_cleanup_stats(self, *, days_back: int = 30) -> Dict[str, int]:
        """Get statistics for cleanup planning."""
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        
        stats = {
            "total_old": self._repo.count_by_status_and_age(older_than=cutoff),
            "pending_old": self._repo.count_by_status_and_age(older_than=cutoff, status=ShareStatus.PENDING),
            "declined_old": self._repo.count_by_status_and_age(older_than=cutoff, status=ShareStatus.DECLINED),
            "canceled_old": self._repo.count_by_status_and_age(older_than=cutoff, status=ShareStatus.CANCELED),
            "expired": self._repo.count_by_status_and_age(older_than=datetime.utcnow()),  # All expired
        }
        
        return stats

    def _can_delete_invite(self, invite: ShareInvite, user_id: str) -> bool:
        """Check if user can delete this invite."""
        # Sender can delete their own invites (except ACCEPTED)
        if invite.sender_user_id == user_id and invite.status != ShareStatus.ACCEPTED:
            return True
        
        # Recipient can delete DECLINED/CANCELED from their inbox
        if (invite.recipient_user_id == user_id and 
            invite.status in [ShareStatus.DECLINED, ShareStatus.CANCELED]):
            return True
        
        return False
