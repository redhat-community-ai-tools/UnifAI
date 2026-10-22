import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from mas.core.hitl.models import ToolAccessMode
from mas.elements.tools.common.base_tool import BaseTool
from .access import ACCESS_REFUSED_PREFIX, ScopeAccessDenied
from .models import FactEntry, MemoryArgs, MemoryEntry, MemoryResponse
from .ports import Embedder, FactStore, MemoryTextStore, ScopeAccessChecker, VectorIndex

logger = logging.getLogger(__name__)


def memory_id_for(text: str) -> str:
    """Deterministic id of a memory: identical (whitespace/case-normalised) text maps to one id."""
    normalised = " ".join(text.split()).casefold()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:32]


MAX_KEY_LENGTH = 200
MAX_VALUE_BYTES = 64 * 1024
PROVENANCE_FIELDS = ("author", "agent", "session_id", "classification")


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _provenance(doc: dict) -> Dict[str, Any]:
    out = {f: doc.get(f) for f in PROVENANCE_FIELDS}
    out["created_at"] = _iso(doc.get("created_at"))
    return out


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
        "and operation 'read' with a query to recall what was remembered before. "
        "Use 'set_fact' / 'get_fact' / 'list_facts' for structured values addressed by a key."
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
        facts: Optional[FactStore] = None,
        author: Optional[str] = None,
        classification: Optional[str] = None,
        access_checker: Optional[ScopeAccessChecker] = None,
    ) -> None:
        if not scope_id:
            raise ValueError("scope_id must not be empty")
        self._scope_id = scope_id
        self._store = store
        self._index = index
        self._embedder = embedder
        self._top_k = top_k
        self._min_score = min_score
        self._facts = facts
        self._author = author
        self._classification = classification
        self._access_checker = access_checker
        self._agent: Optional[str] = None
        self._session_id: Optional[str] = None

    def bind_context(self, session_id: str = "", agent_id: str = "") -> None:
        """Called by agent nodes (see ``bind_tool_context``); fills provenance when available."""
        self._session_id = session_id or None
        self._agent = agent_id or None

    def _provenance(self) -> Dict[str, Optional[str]]:
        return {
            "author": self._author,
            "agent": self._agent,
            "session_id": self._session_id,
            "classification": self._classification,
        }

    def _denial(self, operation: str) -> Optional[Dict[str, Any]]:
        """Check scope access before anything else; None when allowed (or no checker configured)."""
        if self._access_checker is None:
            return None
        try:
            self._access_checker.authorize(self._scope_id)
            return None
        except ScopeAccessDenied as exc:
            message = str(exc)
        except Exception:
            logger.error("memory.access.check_failed", extra={"scope_id": self._scope_id}, exc_info=True)
            message = f"{ACCESS_REFUSED_PREFIX}: access could not be verified"
        logger.warning("memory.access.denied", extra={"scope_id": self._scope_id, "operation": operation})
        return MemoryResponse(success=False, operation=operation, error=message).model_dump()

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        denied = self._denial(str(kwargs.get("operation")))
        if denied is not None:
            return denied
        try:
            args = MemoryArgs(**kwargs)
        except ValueError as exc:
            logger.error("tool.failed", extra={"tool_name": self.name, "error": str(exc)})
            return MemoryResponse(success=False, operation=str(kwargs.get("operation")), error=str(exc)).model_dump()
        try:
            if args.operation == "write":
                return self._write(args)
            if args.operation == "read":
                return self._read(args)
            return self._fact_operation(args)
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
        created = self._store.insert_if_absent(
            self._scope_id, memory_id, text, args.kind, self._provenance(),
        )
        self._index.upsert(self._scope_id, memory_id, vector)
        return MemoryResponse(success=True, operation="write", created=created).model_dump()

    def _read(self, args: MemoryArgs) -> Dict[str, Any]:
        top_k = args.top_k or self._top_k
        query = (args.query or "").strip()
        entries: List[MemoryEntry] = []
        if not query:
            for doc in self._store.list_recent(self._scope_id, top_k):
                entries.append(self._entry(doc))
            return MemoryResponse(success=True, operation="read", memories=entries).model_dump()

        hits = self._index.search(self._scope_id, self._embedder.embed(query), top_k, self._min_score)
        docs = {d["memory_id"]: d for d in self._store.get_many(self._scope_id, [h[0] for h in hits])}
        for memory_id, score in hits:
            doc = docs.get(memory_id)
            if doc is None:
                continue
            entries.append(self._entry(doc, score))
        return MemoryResponse(success=True, operation="read", memories=entries).model_dump()

    @staticmethod
    def _entry(doc: dict, score: Optional[float] = None) -> MemoryEntry:
        return MemoryEntry(
            id=doc["memory_id"], text=doc["text"], kind=doc.get("kind", "fact"), score=score, **_provenance(doc),
        )

    def _fact_operation(self, args: MemoryArgs) -> Dict[str, Any]:
        op = args.operation
        if self._facts is None:
            return MemoryResponse(success=False, operation=op, error="fact store is not configured").model_dump()
        if op == "list_facts":
            docs = self._facts.list(self._scope_id, args.top_k or self._top_k)
            return MemoryResponse(
                success=True, operation=op, facts=[self._fact_entry(d) for d in docs],
            ).model_dump()
        key = (args.key or "").strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            return MemoryResponse(
                success=False, operation=op, error=f"'key' is required and at most {MAX_KEY_LENGTH} characters",
            ).model_dump()
        if op == "get_fact":
            doc = self._facts.get(self._scope_id, key)
            return MemoryResponse(
                success=doc is not None, operation=op,
                facts=[self._fact_entry(doc)] if doc else None,
                error=None if doc else f"no fact stored under key '{key}'",
            ).model_dump()
        # set_fact
        if "value" not in args.model_fields_set:
            return MemoryResponse(success=False, operation=op, error="'value' is required for set_fact").model_dump()
        try:
            encoded = json.dumps(args.value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            return MemoryResponse(success=False, operation=op, error=f"'value' is not valid JSON: {exc}").model_dump()
        if len(encoded.encode("utf-8")) > MAX_VALUE_BYTES:
            return MemoryResponse(
                success=False, operation=op, error=f"'value' exceeds {MAX_VALUE_BYTES} bytes",
            ).model_dump()
        created = self._facts.set(self._scope_id, key, json.loads(encoded), self._provenance())
        return MemoryResponse(success=True, operation=op, created=created).model_dump()

    @staticmethod
    def _fact_entry(doc: dict) -> FactEntry:
        return FactEntry(
            key=doc["key"], value=doc.get("value"),
            **{f: doc.get(f) for f in PROVENANCE_FIELDS},
            created_at=_iso(doc.get("created_at")), updated_at=_iso(doc.get("updated_at")),
        )
