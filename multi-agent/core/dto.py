"""
Database-agnostic DTOs for repository operations.
These models abstract away database-specific formats from business logic.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class GroupedCount(BaseModel):
    """
    Database-agnostic grouped count result.
    
    Abstracts MongoDB's {"_id": {...}, "count": N} format into a clean DTO
    that can work with any database backend.
    
    Example:
        # MongoDB returns: {"_id": {"category": "llm", "type": "openai"}, "count": 5}
        # DTO provides:    GroupedCount(fields={"category": "llm", "type": "openai"}, count=5)
    """
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Grouped field values (e.g., {'category': 'llm', 'type': 'openai'})"
    )
    count: int = Field(
        ...,
        description="Count of documents matching the grouped fields"
    )
    
    def get(self, field: str, default: Any = None) -> Any:
        """
        Get a grouped field value.
        
        Args:
            field: The field name to retrieve
            default: Default value if field doesn't exist
            
        Returns:
            The field value or default
        """
        return self.fields.get(field, default)
    
    def __getitem__(self, field: str) -> Any:
        """Allow dict-like access to fields."""
        return self.fields[field]
    
    def __contains__(self, field: str) -> bool:
        """Allow 'in' operator for checking field existence."""
        return field in self.fields

