"""MongoDB adapter for DataSourceRepository port."""
from typing import Optional, List, Dict, Any

from pymongo.collection import Collection

from core.data_sources.domain.model import DataSource
from core.data_sources.domain.repository import DataSourceRepository
from core.data_sources.domain.view import DataSourceView
from core.pagination.domain.model import PaginatedResult
from infrastructure.mongo.pagination_builder import PaginatedQueryBuilder


class MongoDataSourceRepository(DataSourceRepository):
    """MongoDB implementation of the DataSourceRepository port."""

    _SUMMARY_EXCLUSIONS: Dict[str, Dict[str, int]] = {
        "DOCUMENT": {"type_data.full_text": 0},
        # Future: "SLACK": {"type_data.raw_messages": 0},
    }

    def __init__(self, collection: Collection):
        self._col = collection

    def find_by_id(self, source_id: str) -> Optional[DataSource]:
        """Get source by source_id."""
        doc = self._col.find_one({"source_id": source_id})
        return self._to_model(doc) if doc else None

    def find_by_pipeline_id(self, pipeline_id: str) -> Optional[DataSource]:
        """Get source by pipeline_id."""
        doc = self._col.find_one({"pipeline_id": pipeline_id})
        return self._to_model(doc) if doc else None

    def find_all(
        self,
        source_type: Optional[str] = None,
        view: DataSourceView = DataSourceView.SUMMARY,
    ) -> List[DataSource]:
        """Get all sources, optionally filtered by type.
        
        Args:
            source_type: Filter by source type
            view: SUMMARY excludes heavy fields, FULL returns everything
        """
        query = {"source_type": source_type.upper()} if source_type else {}
        
        # Determine projection based on view
        projection = None
        if view == DataSourceView.SUMMARY and source_type:
            projection = self._SUMMARY_EXCLUSIONS.get(source_type.upper())
        
        docs = self._col.find(query, projection)
        return [self._to_model(doc) for doc in docs]

    def find_paginated(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedResult[Dict[str, Any]]:
        """
        Paginated query for sources using the builder.
        
        Uses PaginatedQueryBuilder for consistent pagination logic.
        """
        builder = (PaginatedQueryBuilder(self._col)
            .with_search(search, field="source_name")
            .with_sort("created_at", desc=True)
            .paginate(cursor, limit))
        
        if source_type:
            builder.with_filter({"source_type": source_type.upper()})
        
        return builder.documents()

    def get_distinct_values(
        self,
        field: str,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> PaginatedResult[str]:
        """
        Get distinct values from a field using the builder.
        
        Uses PaginatedQueryBuilder for consistent pagination logic.
        """
        builder = (PaginatedQueryBuilder(self._col)
            .with_search(search, field=field)
            .with_sort(field, desc=False)  # Alphabetical ascending
            .paginate(cursor, limit))
        
        if source_type:
            builder.with_filter({"source_type": source_type.upper()})
        
        return builder.distinct(field)

    def save(self, source: DataSource) -> None:
        """Insert or update a source (upsert by pipeline_id)."""
        doc = self._to_document(source)
        self._col.update_one(
            {"pipeline_id": source.pipeline_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": source.created_at}
            },
            upsert=True,
        )

    def delete(self, source_id: str) -> bool:
        """Delete source by ID. Returns True if deleted."""
        result = self._col.delete_one({"source_id": source_id})
        return result.deleted_count > 0

    def get_source_by_query(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find sources matching a query dict (for duplicate checking)."""
        try:
            return list(self._col.find(query, {"_id": 0}))
        except Exception:
            return []

    def get_pipeline_status(self, pipeline_id: str) -> Optional[str]:
        """Get pipeline status by looking up the pipelines collection."""
        if not pipeline_id:
            return None
        try:
            # Access sibling collection in same database
            pipeline_col = self._col.database["pipelines"]
            doc = pipeline_col.find_one({"pipeline_id": pipeline_id}, {"status": 1})
            return doc.get("status") if doc else None
        except Exception:
            return None

    # ─── Mapping Methods ──────────────────────────────────────────────────────

    def _to_model(self, doc: Dict[str, Any]) -> DataSource:
        """Convert MongoDB document to domain model."""
        return DataSource.from_dict(doc)

    def _to_document(self, source: DataSource) -> Dict[str, Any]:
        """Convert domain model to MongoDB document."""
        doc = source.to_dict()
        doc.pop("created_at", None)  # Handled separately in upsert
        return doc
