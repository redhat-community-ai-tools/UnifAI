"""Pagination domain models."""
from dataclasses import dataclass
from typing import TypeVar, Generic, List, Optional, Dict, Any

T = TypeVar("T")


@dataclass
class PaginatedResult(Generic[T]):
    """
    Standardized paginated response.
    
    Generic over the data type for type safety.
    Provides consistent structure across all paginated endpoints.
    """
    data: List[T]
    next_cursor: Optional[str]
    has_more: bool
    total: int

    def to_dict(self, data_key: str = "data") -> Dict[str, Any]:
        """
        Convert to API response format with custom data key.
        
        Args:
            data_key: Key name for the data array (e.g., "channels", "documents", "tags")
            
        Returns:
            Dict ready for JSON serialization
        """
        return {
            data_key: self.data,
            "nextCursor": self.next_cursor,
            "hasMore": self.has_more,
            "total": self.total,
        }

    def map(self, fn) -> "PaginatedResult":
        """
        Transform data items while preserving pagination metadata.
        
        Args:
            fn: Function to apply to each item
            
        Returns:
            New PaginatedResult with transformed data
        """
        return PaginatedResult(
            data=[fn(item) for item in self.data],
            next_cursor=self.next_cursor,
            has_more=self.has_more,
            total=self.total,
        )

    def filter(self, predicate) -> "PaginatedResult":
        """
        Filter data items while preserving pagination metadata.
        
        Note: This updates total to reflect filtered count.
        
        Args:
            predicate: Function that returns True for items to keep
            
        Returns:
            New PaginatedResult with filtered data
        """
        filtered = [item for item in self.data if predicate(item)]
        return PaginatedResult(
            data=filtered,
            next_cursor=self.next_cursor,
            has_more=self.has_more,
            total=len(filtered),
        )

