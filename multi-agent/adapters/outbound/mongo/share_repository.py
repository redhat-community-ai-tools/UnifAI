import pymongo
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from mas.sharing.repository.base import ShareRepository
from mas.sharing.models import ShareInvite, ShareStatus, ShareCleanupConfig, ShareCleanupResult
from mas.core.identity import Identity
from global_utils.utils.util import get_mongo_url


class MongoShareRepository(ShareRepository):
    def __init__(self, db_name="UnifAI", coll_name="shares"):
        mongo_uri = get_mongo_url()
        client = pymongo.MongoClient(mongo_uri)
        self._col = client[db_name][coll_name]
        
        self._col.create_index([("share_id", pymongo.ASCENDING)], unique=True)
        self._col.create_index([
            ("recipient_identity.type", 1), ("recipient_identity.id", 1),
            ("status", 1), ("created_at", -1),
        ])
        self._col.create_index([
            ("sender_identity.type", 1), ("sender_identity.id", 1),
            ("status", 1), ("created_at", -1),
        ])
        self._col.create_index("expires_at", expireAfterSeconds=0)

    def save(self, invite: ShareInvite) -> str:
        doc = invite.model_dump(mode="json")
        self._col.insert_one(doc)
        return invite.share_id

    def get(self, share_id: str) -> ShareInvite:
        doc = self._col.find_one({"share_id": share_id})
        if not doc:
            raise KeyError(f"Share invite not found: {share_id}")
        return ShareInvite(**doc)

    def update_status(self, share_id: str, status: ShareStatus, 
                     result_mapping: Optional[dict] = None) -> bool:
        update_doc = {"status": status.value}
        
        if status == ShareStatus.ACCEPTED:
            update_doc["accepted_at"] = datetime.now(timezone.utc)
            if result_mapping:
                update_doc["result_mapping"] = result_mapping
        elif status == ShareStatus.DECLINED:
            update_doc["declined_at"] = datetime.now(timezone.utc)
            
        result = self._col.update_one(
            {"share_id": share_id},
            {"$set": update_doc}
        )
        return result.modified_count == 1

    def list_for_recipient(self, recipient: Identity, 
                          status: Optional[ShareStatus] = None,
                          skip: int = 0, limit: int = 100) -> List[ShareInvite]:
        query = {
            "recipient_identity.type": recipient.type.value,
            "recipient_identity.id": recipient.id,
        }
        if status:
            query["status"] = status.value
            
        cursor = (self._col.find(query)
                 .sort("created_at", pymongo.DESCENDING)
                 .skip(skip)
                 .limit(limit))
        
        return [ShareInvite(**doc) for doc in cursor]

    def list_for_sender(self, sender: Identity,
                       status: Optional[ShareStatus] = None,
                       skip: int = 0, limit: int = 100) -> List[ShareInvite]:
        query = {
            "sender_identity.type": sender.type.value,
            "sender_identity.id": sender.id,
        }
        if status:
            query["status"] = status.value
            
        cursor = (self._col.find(query)
                 .sort("created_at", pymongo.DESCENDING)
                 .skip(skip)
                 .limit(limit))
        
        return [ShareInvite(**doc) for doc in cursor]

    def exists(self, share_id: str) -> bool:
        return self._col.count_documents({"share_id": share_id}, limit=1) == 1

    def delete(self, share_id: str) -> bool:
        """Delete a share invite."""
        result = self._col.delete_one({"share_id": share_id})
        return result.deleted_count == 1

    def cleanup_old_invites(self, config: ShareCleanupConfig) -> ShareCleanupResult:
        """Delete old invites based on configuration."""
        result = ShareCleanupResult(dry_run=config.dry_run)
        
        # Build cleanup rules
        cleanup_rules = []
        
        if config.pending_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=config.pending_days)
            cleanup_rules.append(({"status": ShareStatus.PENDING.value, "created_at": {"$lt": cutoff}}, "pending"))
        
        if config.declined_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=config.declined_days)
            cleanup_rules.append(({"status": ShareStatus.DECLINED.value, "created_at": {"$lt": cutoff}}, "declined"))
        
        if config.canceled_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=config.canceled_days)
            cleanup_rules.append(({"status": ShareStatus.CANCELED.value, "created_at": {"$lt": cutoff}}, "canceled"))
        
        # Process each rule
        for query, status_type in cleanup_rules:
            if config.dry_run:
                count = self._col.count_documents(query)
                result.total_processed += count
                setattr(result, f"{status_type}_count", count)
            else:
                try:
                    delete_result = self._col.delete_many(query)
                    count = delete_result.deleted_count
                    result.total_processed += count
                    result.deleted_count += count
                    setattr(result, f"{status_type}_count", count)
                except Exception as e:
                    result.errors += 1
                    print(f"Error deleting {status_type} invites: {e}")
        
        return result

    def cleanup_expired_invites(self, *, dry_run: bool = False, batch_size: int = 1000) -> ShareCleanupResult:
        """Delete expired invites based on TTL."""
        result = ShareCleanupResult(dry_run=dry_run)
        
        # Find expired invites
        query = {"expires_at": {"$lt": datetime.now(timezone.utc)}}
        
        if dry_run:
            result.expired_count = self._col.count_documents(query)
            result.total_processed = result.expired_count
        else:
            try:
                delete_result = self._col.delete_many(query)
                result.expired_count = delete_result.deleted_count
                result.deleted_count = delete_result.deleted_count
                result.total_processed = delete_result.deleted_count
            except Exception as e:
                result.errors += 1
                print(f"Error deleting expired invites: {e}")
        
        return result

    def count_by_status_and_age(self, *, older_than: datetime, status: Optional[ShareStatus] = None) -> int:
        """Count invites by status and age for cleanup planning."""
        query = {"created_at": {"$lt": older_than}}
        
        if status:
            query["status"] = status.value
        
        return self._col.count_documents(query)
