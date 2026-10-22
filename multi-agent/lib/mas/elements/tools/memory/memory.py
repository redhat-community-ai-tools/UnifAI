import hashlib
import logging
from typing import Any, Dict, List

from mas.core.hitl.models import ToolAccessMode
from mas.elements.tools.common.base_tool import BaseTool
from .models import MemoryArgs, MemoryEntry, MemoryResponse
from .ports import Embedder, MemoryTextStore, VectorIndex

logger = logging.getLogger(__name__)


def memory_id_for(text: str) -> str:
    """Deterministic id of a memory: identical (whitespace/case-normalised) text maps to one id."""
    normalised = " ".join(text.split()).casefold()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:32]


class MemoryTool(BaseTool):
    """Durable memory scoped by a fixed ``scope_id``.

    Text lives in the text store (Mongo), its embedding in the vector index
    (Qdrant). Every query to either is filtered by the scope, and vector hits
    are re-checked against the text store scoped the same way.
    """

    name: str = "memory"
    description: str = (
        "Durable memory shared by every run of the current scope. "
        "Use operation 'write' to remember a fact or decision worth keeping, "
        "and operation 'read' with a query to recall what was remembered before."
    )
    args_schema = MemoryArgs
    access_mode = ToolAccessMode.WRITE

    def __init__(
        self,
        scope_id: str,
        store: MemoryTextStore,
        index: VectorIndex,
        embedder: Embedder,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> None:
        if not scope_id:
            raise ValueError("scope_id must not be empty")
        self._scope_id = scope_id
        self._store = store
        self._index = index
        self._embedder = embedder
        self._top_k = top_k
        self._min_score = min_score

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        try:
            args = MemoryArgs(**kwargs)
        except ValueError as exc:
            logger.error("tool.failed", extra={"tool_name": self.name, "error": str(exc)})
            return MemoryResponse(success=False, operation=str(kwargs.get("operation")), error=str(exc)).model_dump()
        try:
            if args.operation == "write":
                return self._write(args)
            return self._read(args)
        except Exception as exc:
            logger.error(
                "tool.failed",
                extra={"tool_name": self.name, "operation": args.operation, "scope_id": self._scope_id, "error": str(exc)},
            )
            return MemoryResponse(success=False, operation=args.operation, error=str(exc)).model_dump()

    def _write(self, args: MemoryArgs) -> Dict[str, Any]:
        text = (args.text or "").strip()
        if not text:
            return MemoryResponse(success=False, operation="write", error="'text' is required for write").model_dump()
        memory_id = memory_id_for(text)
        # Embed first so a failing embedding service writes nothing. The vector upsert is
        # idempotent and always runs, which also repairs an entry whose vector step failed
        # during an earlier write of the same text.
        vector = self._embedder.embed(text)
        created = self._store.insert_if_absent(self._scope_id, memory_id, text, args.kind)
        self._index.upsert(self._scope_id, memory_id, vector)
        return MemoryResponse(success=True, operation="write", created=created).model_dump()

    def _read(self, args: MemoryArgs) -> Dict[str, Any]:
        top_k = args.top_k or self._top_k
        query = (args.query or "").strip()
        entries: List[MemoryEntry] = []
        if not query:
            for doc in self._store.list_recent(self._scope_id, top_k):
                entries.append(MemoryEntry(id=doc["memory_id"], text=doc["text"], kind=doc.get("kind", "fact")))
            return MemoryResponse(success=True, operation="read", memories=entries).model_dump()

        hits = self._index.search(self._scope_id, self._embedder.embed(query), top_k, self._min_score)
        docs = {d["memory_id"]: d for d in self._store.get_many(self._scope_id, [h[0] for h in hits])}
        for memory_id, score in hits:
            doc = docs.get(memory_id)
            if doc is None:
                continue
            entries.append(
                MemoryEntry(id=memory_id, text=doc["text"], kind=doc.get("kind", "fact"), score=score)
            )
        return MemoryResponse(success=True, operation="read", memories=entries).model_dump()
