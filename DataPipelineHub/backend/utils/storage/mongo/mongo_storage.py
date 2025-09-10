from typing import Any, Dict, List, Optional
from utils.storage.mongo.base import MongoConnection
from utils.storage.mongo.pipelines_repository import PipelinesRepository
from utils.storage.mongo.sources_repository import SourcesRepository
from utils.storage.mongo.slack_channels_repository import SlackChannelsRepository
from utils.storage.mongo.utils import make_json_safe
from pymongo import UpdateOne
from config.constants import Database, Collection as CollectionName
from config.constants import PipelineStatus
from datetime import datetime, timezone

class MongoStorage:
    """Main MongoDB storage facade that composes repositories."""
    
    def __init__(self, mongo_uri: str):
        conn = MongoConnection(mongo_uri)
        
        self.sources = SourcesRepository(
            conn.get_collection(Database.DATA_SOURCES.value, CollectionName.SOURCES.value, [("source_id", True)])
        )
        self.pipelines = PipelinesRepository(
            conn.get_collection(Database.PIPELINE.value, CollectionName.PIPELINES.value, [("pipeline_id", True)])
        )
        self.slack_channels = SlackChannelsRepository(
            conn.get_collection(Database.DATA_SOURCES.value, CollectionName.SLACK_CHANNELS.value, [("project_id", False), ("channel_id", False)])
        )
        
        self._conn = conn

    def get_all_sources(self, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all sources (delegates to sources repository)."""
        return self.sources.get_all(source_type)

    def get_source_by_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get sources by query (delegates to sources repository)."""
        return self.sources.get_by_query(query)

    def get_source_info(self, source_id: str) -> Dict[str, Any]:
        """Get source info (delegates to sources repository)."""
        return self.sources.get_info(source_id)

    def get_source_info_by_pipeline_id(self, pipeline_id: str) -> Dict[str, Any]:
        """Get source info by pipeline_id (delegates to sources repository)."""
        return self.sources.get_info_by_pipeline_id(pipeline_id)

    def get_source_info_by_source_id(self, source_id: str) -> Dict[str, Any]:
        """Get source info by source_id (delegates to sources repository)."""
        return self.sources.get_info_by_source_id(source_id)

    def delete_sources(self, filter_query: Dict[str, Any]) -> Dict[str, Any]:
        """Generic delete for sources by arbitrary filter."""
        return self.sources.delete(filter_query)

    def upsert_source_summary(self, source_id: str, source_name: str, source_type: str,
                              upload_by: str, pipeline_id: str, type_data: Optional[Dict[str, Any]] = None) -> None:
        """Create/update source summary (delegates to sources repository)."""
        return self.sources.upsert_summary(source_id, source_name, source_type, upload_by, pipeline_id, type_data)

    def get_pipeline_stats(self, pipeline_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get pipeline stats (delegates to pipelines repository)."""
        return self.pipelines.get_stats(pipeline_ids)

    def delete_pipelines(self, filter_query: Dict[str, Any]) -> Dict[str, Any]:
        """Generic delete for pipelines by arbitrary filter."""
        return self.pipelines.delete(filter_query)

    def get_all(self, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Alias for get_all_sources to maintain SourceRepository interface compatibility."""
        return self.get_all_sources(source_type)

    def list_sources(self, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all sources enriched with pipeline stats (for backward compatibility)."""
        sources = self.sources.get_all(source_type)
        pipeline_ids = [s.get('pipeline_id') for s in sources if s.get('pipeline_id')]
        valid_ids = [pid for pid in pipeline_ids if pid is not None]
        pipeline_stats = self.pipelines.get_stats(valid_ids)
        
        enriched = []
        for source in sources:
            pipeline_id = source.get('pipeline_id')
            if pipeline_id and pipeline_id in pipeline_stats:
                source['pipeline_stats'] = pipeline_stats[pipeline_id]
                source['status'] = pipeline_stats[pipeline_id].get('status')
            else:
                source['pipeline_stats'] = None
                source['status'] = None
            enriched.append(make_json_safe(source))
        
        # Prefer last_updated for ordering if present; fallback to created_at
        def _sort_key(s: Dict[str, Any]):
            last_updated = s.get('last_updated')
            created_at = s.get('created_at')
            return last_updated or created_at or 0

        enriched_sorted = sorted(enriched, key=_sort_key, reverse=True)
        return enriched_sorted

    def upsert_documents(self, db: str, col: str, docs: List[Dict[str, Any]], key_field: str) -> None:
        """Generic document upsert operation."""
        collection = self._conn.get_collection(db, col)
        ops = [
            UpdateOne({key_field: doc[key_field]}, {'$set': doc}, upsert=True)
            for doc in docs if key_field in doc
        ]
        if ops:
            collection.bulk_write(ops)

    def find_documents(self, db: str, col: str, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Generic document find operation."""
        return list(self._conn.get_collection(db, col).find(query or {}))

    def find_duplicate_source_by_md5(self, content_md5: str, source_type: str) -> Optional[Dict[str, Any]]:
        """Return the first existing source that has the same MD5 and whose pipeline is DONE."""
        query: Dict[str, Any] = {"type_data.content_md5": content_md5}
        if source_type:
            query["source_type"] = source_type
        candidates = list(self._conn.get_collection(Database.DATA_SOURCES.value, CollectionName.SOURCES.value).find(query))
        for existing in candidates:
            pipeline_id = existing.get("pipeline_id")
            if not pipeline_id:
                continue
            status = self.pipelines.get_status(pipeline_id)
            if status == PipelineStatus.DONE.value:
                return existing
        return None

    def mark_pipeline_skipped(self, pipeline_id: str) -> bool:
        return self.pipelines.update_status(pipeline_id, PipelineStatus.SKIPPED.value)

    def find_sources_by_content_md5(self, content_md5: str, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.sources.find_by_content_md5(content_md5, source_type)

    def update_sources(self, filter_query: Dict[str, Any], update_ops: Any, many: bool = False, upsert: bool = False) -> Dict[str, Any]:
        """Generic update for sources repository."""
        return self.sources.update(filter_query, update_ops, many=many, upsert=upsert)

    def update_pipelines(self, filter_query: Dict[str, Any], update_ops: Any, many: bool = False, upsert: bool = False) -> Dict[str, Any]:
        """Generic update for pipelines repository."""
        return self.pipelines.update(filter_query, update_ops, many=many, upsert=upsert)

    def handle_document_duplicate(
        self,
        original_doc: Dict[str, Any],
        duplicate_pipeline_id: str,
        duplicate_source_name: str,
        uploader: str,
    ) -> None:
        """One-shot handler to resolve a duplicate document pipeline."""
        try:
            # 1) Mark duplicate pipeline as skipped
            self.mark_pipeline_skipped(duplicate_pipeline_id)

            # 2) Fetch duplicate doc created_at if present
            col = self._conn.get_collection(Database.DATA_SOURCES.value, CollectionName.SOURCES.value)
            dup_doc = col.find_one({"pipeline_id": duplicate_pipeline_id}, {"created_at": 1}) or {}
            duplicate_created_at = dup_doc.get("created_at", datetime.now(timezone.utc))

            # 3) Update original doc with duplication notice, updated creation time and merged uploader
            update_pipeline = [{"$set": {"last_updated": duplicate_created_at, "upload_by": {
                "$cond": [
                    {"$isArray": "$upload_by"},
                    {"$setUnion": ["$upload_by", [uploader]]},
                    {"$cond": [
                        {"$eq": ["$upload_by", uploader]},
                        "$upload_by",
                        ["$upload_by", uploader]
                    ]}
                ]}, "duplication_notice": {
                    "duplicate_uploaded_name": duplicate_source_name,
                    "existing_name": original_doc.get("source_name", ""),
                    "duplicate_at": duplicate_created_at
                }} }]
            self.update_sources({"pipeline_id": original_doc.get("pipeline_id", "")}, update_pipeline, many=False, upsert=False)

            # 4) Delete duplicate source and pipeline docs
            self.delete_sources({"pipeline_id": duplicate_pipeline_id})
            self.delete_pipelines({"pipeline_id": duplicate_pipeline_id})
        except Exception:
            pass
