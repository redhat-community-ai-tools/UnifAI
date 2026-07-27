from abc import ABC, abstractmethod
from typing import Optional


class KVStore(ABC):
    """Outbound port: string key-value storage (Redis, in-memory, etc.)."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Return value or None if key is missing."""

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        """Store value; optional TTL in seconds (Redis EX)."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove key if present."""
