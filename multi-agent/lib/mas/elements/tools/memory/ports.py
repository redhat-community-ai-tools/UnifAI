"""Ports of the memory tool: text store, vector index and embedder."""
from typing import Any, Dict, List, Optional, Protocol, Tuple


class MemoryTextStore(Protocol):
    def insert_if_absent(
        self, scope_id: str, memory_id: str, text: str, kind: str, provenance: Dict[str, Optional[str]],
    ) -> bool:
        """Store the entry; return False when (scope_id, memory_id) already exists."""
        ...

    def get_many(self, scope_id: str, memory_ids: List[str]) -> List[dict]:
        """Return the stored entries of *scope_id* among *memory_ids*."""
        ...

    def list_recent(self, scope_id: str, limit: int) -> List[dict]:
        """Return the most recently written entries of *scope_id*."""
        ...


class FactStore(Protocol):
    """Structured facts: one JSON value per (scope_id, key), last write wins."""

    def set(
        self, scope_id: str, key: str, value: Any, provenance: Dict[str, Optional[str]],
    ) -> bool:
        """Upsert the fact; return True when the key did not exist yet."""
        ...

    def get(self, scope_id: str, key: str) -> Optional[dict]: ...

    def list(self, scope_id: str, limit: int) -> List[dict]:
        """Most recently updated facts of *scope_id*."""
        ...


class VectorIndex(Protocol):
    def upsert(self, scope_id: str, memory_id: str, vector: List[float]) -> None: ...

    def search(
        self, scope_id: str, vector: List[float], top_k: int, min_score: float,
    ) -> List[Tuple[str, float]]:
        """Return (memory_id, score) pairs of *scope_id* only, best first."""
        ...


class Embedder(Protocol):
    def embed(self, text: str) -> List[float]: ...


class ScopeAccessChecker(Protocol):
    """Decides whether the acting user may use a memory scope. Must fail closed."""

    def authorize(self, scope_id: str) -> None:
        """Return normally when access is granted; raise ``ScopeAccessDenied`` otherwise.

        Any other exception raised here is treated as a denial by the tool.
        """
        ...
