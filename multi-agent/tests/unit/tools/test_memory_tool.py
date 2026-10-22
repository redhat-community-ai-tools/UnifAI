"""Unit tests of the scoped memory tool, with in-memory fakes for Mongo, Qdrant and embeddings."""
import math
from typing import List, Tuple

import pytest
from pydantic import ValidationError

from mas.elements.tools.memory.config import MemoryToolConfig
from mas.elements.tools.memory.memory import MemoryTool, memory_id_for
from mas.elements.tools.memory.memory_factory import MemoryToolFactory
from mas.elements.tools.types import ToolsSpec  # noqa: F401  (import guards the discriminated union)


class FakeStore:
    def __init__(self) -> None:
        self.docs: List[dict] = []

    def insert_if_absent(self, scope_id, memory_id, text, kind):
        if any(d["scope_id"] == scope_id and d["memory_id"] == memory_id for d in self.docs):
            return False
        self.docs.append({"scope_id": scope_id, "memory_id": memory_id, "text": text, "kind": kind})
        return True

    def get_many(self, scope_id, memory_ids):
        return [d for d in self.docs if d["scope_id"] == scope_id and d["memory_id"] in memory_ids]

    def list_recent(self, scope_id, limit):
        return [d for d in reversed(self.docs) if d["scope_id"] == scope_id][:limit]


class FakeIndex:
    """Cosine index over a dict. Deliberately shared between tools so isolation is the tool's doing."""

    def __init__(self) -> None:
        self.points: dict = {}

    def upsert(self, scope_id, memory_id, vector):
        self.points[(scope_id, memory_id)] = vector

    def search(self, scope_id, vector, top_k, min_score) -> List[Tuple[str, float]]:
        scored = [(mid, _cos(vector, v)) for (sid, mid), v in self.points.items() if sid == scope_id]
        return sorted([s for s in scored if s[1] >= min_score], key=lambda s: -s[1])[:top_k]


def _cos(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


class FakeEmbedder:
    """Bag-of-keywords embedding: deterministic and good enough to rank."""
    VOCAB = ("openshift", "postgres", "budget", "deadline")

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        t = text.lower()
        return [float(t.count(w)) for w in self.VOCAB] + [0.01]


@pytest.fixture
def backend():
    return FakeStore(), FakeIndex(), FakeEmbedder()


def make_tool(scope, backend, **kw):
    store, index, embedder = backend
    return MemoryTool(scope, store, index, embedder, **kw)


def test_write_then_read_round_trip(backend):
    tool = make_tool("p1", backend)
    assert tool.run(operation="write", text="The cluster runs OpenShift 4.22")["created"] is True
    tool.run(operation="write", text="Budget approved for Postgres licences", kind="decision")
    out = tool.run(operation="read", query="which openshift version")
    assert out["success"] is True
    assert out["memories"][0]["text"] == "The cluster runs OpenShift 4.22"
    assert out["memories"][0]["kind"] == "fact"


def test_read_without_query_returns_most_recent_first(backend):
    tool = make_tool("p1", backend)
    tool.run(operation="write", text="first note")
    tool.run(operation="write", text="second note")
    out = tool.run(operation="read", top_k=1)
    assert [m["text"] for m in out["memories"]] == ["second note"]


def test_scope_isolation_between_tools_sharing_backends(backend):
    a, b = make_tool("project-a", backend), make_tool("project-b", backend)
    a.run(operation="write", text="Deadline is Friday for project A")
    b.run(operation="write", text="Deadline is Monday for project B")
    for tool, expected in ((a, "project A"), (b, "project B")):
        texts = [m["text"] for m in tool.run(operation="read", query="deadline")["memories"]]
        assert len(texts) == 1 and expected in texts[0]
        recent = [m["text"] for m in tool.run(operation="read")["memories"]]
        assert recent == texts


def test_scope_cannot_be_chosen_by_the_model(backend):
    a = make_tool("project-a", backend)
    make_tool("project-b", backend).run(operation="write", text="secret deadline of B")
    # an extra scope-like argument is not part of the schema and must not widen the read
    out = a.run(operation="read", query="deadline", scope_id="project-b")
    assert out["memories"] == []


def test_vector_hit_missing_from_scoped_store_is_dropped(backend):
    store = backend[0]
    tool = make_tool("p1", backend)
    tool.run(operation="write", text="OpenShift note")
    store.docs.clear()  # index entry survives without its text
    assert tool.run(operation="read", query="openshift")["memories"] == []


def test_dedup_same_scope_ignores_case_and_whitespace(backend):
    store, index, _ = backend
    tool = make_tool("p1", backend)
    assert tool.run(operation="write", text="Uses  Postgres")["created"] is True
    assert tool.run(operation="write", text="uses postgres ")["created"] is False
    assert len(store.docs) == 1 and len(index.points) == 1


def test_same_text_in_two_scopes_is_stored_twice(backend):
    store, _, _ = backend
    make_tool("a", backend).run(operation="write", text="same text")
    assert make_tool("b", backend).run(operation="write", text="same text")["created"] is True
    assert len(store.docs) == 2
    assert memory_id_for("same text") == memory_id_for("  SAME   text")


def test_embedding_failure_writes_nothing_and_reports_error(backend):
    store, index, embedder = backend

    def boom(_):
        raise RuntimeError("embedding service down")
    embedder.embed = boom
    out = make_tool("p1", backend).run(operation="write", text="x")
    assert out["success"] is False and "embedding service down" in out["error"]
    assert store.docs == [] and index.points == {}


def test_write_requires_text_and_bad_args_are_reported(backend):
    tool = make_tool("p1", backend)
    assert tool.run(operation="write", text="  ")["success"] is False
    assert tool.run(operation="forget")["success"] is False


def test_min_score_filters_weak_hits(backend):
    tool = make_tool("p1", backend, min_score=0.9)
    tool.run(operation="write", text="OpenShift and Postgres")
    assert tool.run(operation="read", query="budget")["memories"] == []


def test_empty_scope_is_rejected(backend):
    with pytest.raises(ValueError):
        make_tool("", backend)
    with pytest.raises(ValidationError):
        MemoryToolConfig(scope_id="")


def test_factory_builds_tool_from_config_with_injected_backends(backend):
    store, index, embedder = backend
    cfg = MemoryToolConfig(scope_id="p9", top_k=3)
    factory = MemoryToolFactory()
    assert factory.accepts(cfg, "memory")
    tool = factory.create(cfg, store=store, index=index, embedder=embedder)
    tool.run(operation="write", text="Budget note")
    assert store.docs[0]["scope_id"] == "p9"
