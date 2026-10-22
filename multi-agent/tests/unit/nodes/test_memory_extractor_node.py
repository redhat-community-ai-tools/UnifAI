"""MemoryExtractorNode: wiring, classification fallback and never raising on bad model output."""
import json
import sys
from pathlib import Path

import pytest

from mas.blueprints.models.blueprint import ResourceSpec
from mas.catalog.element_registry import ElementRegistry
from mas.core.enums import ResourceCategory
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.nodes.memory_extractor.config import MemoryExtractorNodeConfig
from mas.elements.nodes.memory_extractor.memory_extractor import MemoryExtractorNode
from mas.elements.nodes.memory_extractor.memory_extractor_node_factory import MemoryExtractorNodeFactory
from mas.elements.nodes.types import NodeSpec
from mas.elements.tools.memory.access import TeamScopeAccessChecker
from mas.elements.tools.memory.memory import MemoryTool
from mas.graph.state.graph_state import Channel, GraphState
from mas.graph.state.state_view import StateView
from pydantic import TypeAdapter

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from test_memory_extraction import FakeLLM, GOOD  # noqa: E402
from test_memory_access import FakeProvider, holder_for  # noqa: E402
from test_memory_tool import FakeEmbedder, FakeFacts, FakeIndex, FakeStore  # noqa: E402

MSGS = [
    ChatMessage(role=Role.USER, content="We chose Postgres 17. Deadline is Friday."),
    ChatMessage(role=Role.ASSISTANT, content="Noted."),
]


def tool(checker=None):
    return MemoryTool("proj", FakeStore(), FakeIndex(), FakeEmbedder(), facts=FakeFacts(), access_checker=checker)


def node(llm, memory=None, **kw):
    return MemoryExtractorNode(
        llm=llm, memory=memory or tool(), restricted_classifications=["restricted"], **kw,
    )


def test_extracts_and_persists_through_the_tool():
    memory = tool()
    summary = node(FakeLLM(GOOD), memory).extract_and_persist(MSGS)
    assert summary.startswith("memory extraction ok: 1 facts, 1 memories written")
    assert memory.run(operation="get_fact", key="db.engine")["success"]


def test_accepts_dict_messages():
    summary = node(FakeLLM(GOOD)).extract_and_persist([{"role": "user", "content": "hello"}, 42])
    assert "ok" in summary


@pytest.mark.parametrize("answer", ["not json", "[1, 2]", "", json.dumps({"facts": "x"})])
def test_bad_model_output_does_not_raise(answer):
    memory = tool()
    summary = node(FakeLLM(answer), memory).extract_and_persist(MSGS)
    assert isinstance(summary, str)
    assert memory.run(operation="list_facts")["success"]


def test_model_failure_does_not_raise():
    summary = node(FakeLLM(error=RuntimeError("boom"))).extract_and_persist(MSGS)
    assert summary.startswith("memory extraction failed")


def test_unexpected_exception_does_not_raise():
    class Broken:
        def run(self, **kw):
            raise RuntimeError("down")

    assert node(FakeLLM(GOOD), Broken()).extract_and_persist(MSGS).startswith("memory extraction")


def test_access_refusal_is_reported_and_nothing_written():
    memory = tool(TeamScopeAccessChecker(FakeProvider(), holder_for("alice")))
    summary = node(FakeLLM(GOOD), memory).extract_and_persist(MSGS)
    assert "incomplete" in summary and "memory access refused" in summary and "0 facts, 0 memories" in summary


def test_restricted_classification_uses_the_local_llm_only():
    default, local = FakeLLM(GOOD, label="default"), FakeLLM(GOOD, label="local")
    summary = node(default, local_llm=local, classification="Restricted").extract_and_persist(MSGS)
    assert "ok" in summary and local.seen and not default.seen


def test_restricted_classification_without_local_llm_refuses():
    default = FakeLLM(GOOD)
    memory = tool()
    summary = node(default, memory, classification="restricted").extract_and_persist(MSGS)
    assert summary.startswith("memory extraction failed") and "approved" in summary
    assert not default.seen
    assert memory.run(operation="get_fact", key="db.engine")["success"] is False


def test_unrestricted_classification_uses_the_default_llm():
    default, local = FakeLLM(GOOD), FakeLLM(GOOD)
    node(default, local_llm=local, classification="internal").extract_and_persist(MSGS)
    assert default.seen and not local.seen


def test_run_writes_the_summary_to_the_nodes_output_channel():
    n = node(FakeLLM(GOOD))
    gs = GraphState(messages=MSGS)
    view = StateView(gs, reads=MemoryExtractorNode.total_reads(), writes=MemoryExtractorNode.total_writes())
    n.run(view)
    assert any("memory extraction ok" in v for v in gs.nodes_output.values())


def test_binds_session_and_node_provenance():
    memory = tool()
    holder = holder_for("alice")
    node(FakeLLM(GOOD), memory, execution_holder=holder).extract_and_persist(MSGS)
    fact = memory.run(operation="get_fact", key="db.engine")["facts"][0]
    assert fact["session_id"] == "s" and fact["agent"] == "memory_extractor"


def test_config_in_blueprint_union_and_defaults():
    cfg = TypeAdapter(NodeSpec).validate_python(
        {"type": "memory_extractor_node", "llm": "m", "memory": "mem"}
    )
    assert isinstance(cfg, MemoryExtractorNodeConfig)
    assert cfg.classification is None and cfg.local_llm is None
    assert "restricted" in cfg.restricted_classifications
    with pytest.raises(Exception):
        MemoryExtractorNodeConfig(llm="m")  # memory is required
    with pytest.raises(Exception):
        MemoryExtractorNodeConfig(llm="m", memory="t", scope_id="x")  # scope lives on the tool


def test_spec_is_discovered_and_factory_builds_the_node():
    reg = ElementRegistry()
    reg.auto_discover()
    assert reg.get_spec(ResourceCategory.NODE, "memory_extractor_node")
    cfg = MemoryExtractorNodeConfig(llm="m", memory="mem", classification="restricted")
    built = MemoryExtractorNodeFactory().create(
        cfg, deps=None, llm=FakeLLM(GOOD), memory=tool(), local_llm=None,
    )
    assert isinstance(built, MemoryExtractorNode)
    assert built.extract_and_persist(MSGS).startswith("memory extraction failed")
    assert MemoryExtractorNodeFactory().accepts(cfg, "memory_extractor_node")
