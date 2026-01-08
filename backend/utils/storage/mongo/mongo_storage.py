from typing import Any, Dict, List, Optional
from utils.storage.mongo.base import MongoConnection
from utils.storage.mongo.pipelines_repository import PipelinesRepository
from utils.storage.mongo.sources_repository import SourcesRepository
from utils.storage.mongo.slack_channels_repository import SlackChannelsRepository
from utils.storage.mongo.terms_user_approval_repository import TermsUserApprovalRepository
from utils.storage.mongo.utils import make_json_safe
from pymongo import UpdateOne
from config.constants import Database, Collection as CollectionName

class MongoStorage:
    """Main MongoDB storage facade that composes repositories."""
    
    def __init__(self, mongo_uri: str):
        conn = MongoConnection(mongo_uri)
        
        self.sources = SourcesRepository(
            conn.get_collection(
                Database.DATA_SOURCES.value,
                CollectionName.SOURCES.value,
                [("source_id", True), ("type_data.md5", False)]
            )
        )
        self.pipelines = PipelinesRepository(
            conn.get_collection(Database.PIPELINE.value, CollectionName.PIPELINES.value, [("pipeline_id", True)])
        )
        self.slack_channels = SlackChannelsRepository(
            conn.get_collection(Database.DATA_SOURCES.value, CollectionName.SLACK_CHANNELS.value, [("project_id", False), ("channel_id", False)])
        )
        self.terms_user_approval = TermsUserApprovalRepository(
            conn.get_collection(Database.USERS.value, CollectionName.TERMS_USER_APPROVAL.value, [("username", True)])
        )
        
        self._conn = conn

    def get_all_sources(self, source_type: Optional[str] = None, projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all sources (delegates to sources repository)."""
        return self.sources.get_all(source_type, projection)

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

    def delete_source(self, source_id: str) -> Dict[str, Any]:
        """Delete source (delegates to sources repository)."""
        return self.sources.delete(source_id)

    def update_source(self, source_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update source (delegates to sources repository)."""
        return self.sources.update(source_id, updates)

    def upsert_source_summary(self, source_id: str, source_name: str, source_type: str,
                              upload_by: str, pipeline_id: str, type_data: Optional[Dict[str, Any]] = None, tags: List[str] = None) -> None:
        """Create/update source summary (delegates to sources repository)."""
        return self.sources.upsert_summary(source_id, source_name, source_type, upload_by, pipeline_id, type_data, tags)

    def get_pipeline_stats(self, pipeline_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get pipeline stats (delegates to pipelines repository)."""
        return self.pipelines.get_stats(pipeline_ids)

    def get_pipeline_status(self, pipeline_id: str) -> str:
        """Get single pipeline status (delegates to pipelines repository)."""
        return self.pipelines.get_status(pipeline_id)

    def delete_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """Delete pipeline (delegates to pipelines repository)."""
        return self.pipelines.delete(pipeline_id)

    def get_all(self, source_type: Optional[str] = None, projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Alias for get_all_sources to maintain SourceRepository interface compatibility."""
        return self.get_all_sources(source_type, projection)

    def get_paginated(
        self,
        field_path: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
        search_regex: Optional[str] = None,
        match_filter: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: int = -1
    ) -> Dict[str, Any]:
        """Generic paginated query (delegates to sources repository)."""
        return self.sources.get_paginated(
            field_path=field_path,
            cursor=cursor,
            limit=limit,
            search_regex=search_regex,
            match_filter=match_filter,
            sort_by=sort_by,
            sort_order=sort_order
        )

    def get_sources_paginated(self, cursor: Optional[str] = None, limit: int = 50, search_regex: Optional[str] = None, source_type: Optional[str] = None) -> Dict[str, Any]:
        """Get sources with pagination and pipeline stats enrichment."""
        match_filter = {"source_type": source_type.upper()} if source_type else None
        result = self.sources.get_paginated(
            field_path=None,
            cursor=cursor,
            limit=limit,
            search_regex=search_regex,
            match_filter=match_filter,
        )
        sources = result.get("data", [])
        
        # Enrich with pipeline stats
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
            
        result["sources"] = enriched
        del result["data"]
        return result

    def list_sources(self, source_type: Optional[str] = None, projection: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all sources enriched with pipeline stats.
        
        Args:
            source_type: Optional filter by source type
            projection: Optional MongoDB projection
        """
        sources = self.sources.get_all(source_type, projection=projection)
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
        
        enriched_sorted = sorted(
            enriched,
            key=lambda s: s.get('created_at') or 0,  # default to 0 if created_at is missing
            reverse=True
        )
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
