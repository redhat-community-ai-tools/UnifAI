"""Ports of the memory tool: text store, vector index and embedder."""
from typing import List, Protocol, Tuple


class MemoryTextStore(Protocol):
    def insert_if_absent(self, scope_id: str, memory_id: str, text: str, kind: str) -> bool:
        """Store the entry; return False when (scope_id, memory_id) already exists."""
        ...

    def get_many(self, scope_id: str, memory_ids: List[str]) -> List[dict]:
        """Return the stored entries of *scope_id* among *memory_ids*."""
        ...

    def list_recent(self, scope_id: str, limit: int) -> List[dict]:
        """Return the most recently written entries of *scope_id*."""
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
