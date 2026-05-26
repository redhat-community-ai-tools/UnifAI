"""
MongoDB implementation of template repository.

Follows the pattern established by MongoBlueprintRepository.
"""
import pymongo
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Optional

from mas.templates.repository.repository import TemplateRepository
from mas.templates.models.template import Template
from global_utils.utils.util import get_mongo_url


class MongoTemplateRepository(TemplateRepository):
    """
    MongoDB-backed template storage.

    Uses the same patterns as MongoBlueprintRepository for consistency.
    """

    def __init__(
        self,
        db_name: str = "UnifAI",
        coll_name: str = "templates",
    ):
        mongo_uri = get_mongo_url()
        client = pymongo.MongoClient(mongo_uri)
        self._col = client[db_name][coll_name]
        
        # Indexes
        self._col.create_index([("template_id", pymongo.ASCENDING)], unique=True)
        self._col.create_index("metadata.is_public")
        self._col.create_index("metadata.category")
        self._col.create_index("metadata.tags")
        self._col.create_index([
            ("draft.name", pymongo.TEXT),
            ("draft.description", pymongo.TEXT),
        ])

    # ────────────────────────────── Writes ──────────────────────────────
    def save(self, template: Template) -> str:
        """Persist a template and return its ID."""
        # Generate ID if not provided
        template_id = template.template_id or str(uuid4())
        
        # Check for existing
        if self._col.count_documents({"template_id": template_id}, limit=1) > 0:
            raise ValueError(f"Template already exists: {template_id}")
        
        doc = self._template_to_doc(template, template_id)
        self._col.insert_one(doc)
        return template_id

    def update(self, template: Template) -> bool:
        """Update an existing template."""
        if not self.exists(template.template_id):
            raise KeyError(f"Template not found: {template.template_id}")
        
        doc = self._template_to_doc(template, template.template_id)
        doc["updated_at"] = datetime.now(timezone.utc)
        
        res = self._col.update_one(
            {"template_id": template.template_id},
            {"$set": doc}
        )
        return res.modified_count == 1

    def delete(self, template_id: str) -> bool:
        """Delete a template by ID."""
        res = self._col.delete_one({"template_id": template_id})
        return res.deleted_count == 1

    # ────────────────────────────── Reads ───────────────────────────────
    def get(self, template_id: str) -> Template:
        """Load a template by ID."""
        doc = self._col.find_one({"template_id": template_id})
        if not doc:
            raise KeyError(f"Template not found: {template_id}")
        return self._doc_to_template(doc)

    def exists(self, template_id: str) -> bool:
        """Check if a template exists."""
        return self._col.count_documents({"template_id": template_id}, limit=1) == 1

    # ────────────────────────────── Listings ────────────────────────────
    def list_templates(
        self,
        *,
        is_public: Optional[bool] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100,
        sort_desc: bool = True,
    ) -> List[Template]:
        """List templates with optional filtering."""
        query = self._build_filter(is_public, category, tags)
        
        cursor = (
            self._col.find(query)
            .sort("created_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        
        return [self._doc_to_template(doc) for doc in cursor]

    def count(
        self,
        *,
        is_public: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> int:
        """Count templates matching filter criteria."""
        query = self._build_filter(is_public, category)
        return self._col.count_documents(query)

    # ────────────────────────────── Search ──────────────────────────────
    def search(
        self,
        query: str,
        *,
        is_public: Optional[bool] = True,
        limit: int = 20,
    ) -> List[Template]:
        """Search templates by name/description using text index."""
        search_query: dict = {"$text": {"$search": query}}
        
        if is_public is not None:
            search_query["metadata.is_public"] = is_public
        
        cursor = (
            self._col.find(search_query)
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
        
        return [self._doc_to_template(doc) for doc in cursor]

    # ────────────────────────────── Helpers ─────────────────────────────
    def _build_filter(
        self,
        is_public: Optional[bool] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> dict:
        """Build MongoDB filter from criteria."""
        query: dict = {}
        
        if is_public is not None:
            query["metadata.is_public"] = is_public
        if category is not None:
            query["metadata.category"] = category
        if tags:
            query["metadata.tags"] = {"$in": tags}
        
        return query

    def _template_to_doc(self, template: Template, template_id: str) -> dict:
        """Convert Template model to MongoDB document."""
        data = template.model_dump(mode="json")
        data["template_id"] = template_id
        return data

    def _doc_to_template(self, doc: dict) -> Template:
        """Convert MongoDB document to Template model."""
        # Remove MongoDB _id
        doc.pop("_id", None)
        return Template(**doc)
