"""
Abstract template repository interface.

Defines the contract for template persistence.
Following the Repository Pattern (DIP - Dependency Inversion Principle).
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from mas.templates.models.template import Template


class TemplateRepository(ABC):
    """
    Abstract interface for template storage.
    
    Implementations can use MongoDB, PostgreSQL, in-memory, etc.
    Services depend on this interface, not concrete implementations.
    """

    # ────────────────────────────── Writes ──────────────────────────────
    @abstractmethod
    def save(self, template: Template) -> str:
        """
        Persist a template and return its ID.
        
        If template_id already exists, raises ValueError.
        Use update() to modify existing templates.
        """

    @abstractmethod
    def update(self, template: Template) -> bool:
        """
        Update an existing template.
        
        Returns True if a document was modified.
        Raises KeyError if template doesn't exist.
        """

    @abstractmethod
    def delete(self, template_id: str) -> bool:
        """
        Soft-delete a template by ID (marks deleted=True).
        
        Returns True if a document was marked deleted.
        The document stays in the database so the seeder
        knows not to re-insert fixture templates.
        """

    # ────────────────────────────── Reads ───────────────────────────────
    @abstractmethod
    def get(self, template_id: str) -> Template:
        """
        Load a template by ID.
        
        Raises KeyError if not found.
        """

    @abstractmethod
    def exists(self, template_id: str, *, include_deleted: bool = False) -> bool:
        """Check if a template exists.

        Args:
            template_id: The template identifier.
            include_deleted: If ``True``, soft-deleted templates are
                counted as existing (used by the fixture seeder to
                avoid re-inserting admin-deleted templates).
        """

    # ────────────────────────────── Listings ────────────────────────────
    @abstractmethod
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
        """
        List templates with optional filtering.
        
        Args:
            is_public: Filter by public status
            category: Filter by template category
            tags: Filter by tags (any match)
            skip: Pagination offset
            limit: Max results
            sort_desc: Sort by created_at descending
            
        Returns:
            List of matching templates
        """

    @abstractmethod
    def count(
        self,
        *,
        is_public: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> int:
        """Count templates matching filter criteria."""

    # ────────────────────────────── Search ──────────────────────────────
    @abstractmethod
    def search(
        self,
        query: str,
        *,
        is_public: Optional[bool] = True,
        limit: int = 20,
    ) -> List[Template]:
        """
        Search templates by name/description.
        
        Uses text search for fuzzy matching.
        """
