"""LLM response metadata reaches the final assistant message unchanged."""

from mas.elements.llms.common.chat.message import RESPONSE_METADATA_KEY, ChatMessage
from mas.elements.nodes.common.workload import AgentResult
from mas.elements.nodes.final_answer.final_answer import FinalAnswerNode


def _node(*results):
    node = FinalAnswerNode.__new__(FinalAnswerNode)
    node._collected_results = list(results)
    return node


def _res(content, meta=None):
    return AgentResult(content=content, agent_id="a", agent_name="A", execution_metadata=meta or {})


def test_single_result_with_metadata_becomes_message_with_metadata():
    entry = {"response_id": "r", "model": "m", "fields": {"x_provider": "p"}}
    node = _node(_res("hi", {RESPONSE_METADATA_KEY: entry}))
    out = node._as_message("hi")
    assert isinstance(out, ChatMessage)
    assert out.metadata[RESPONSE_METADATA_KEY] == entry


def test_without_metadata_the_plain_string_is_kept():
    node = _node(_res("hi"))
    assert node._as_message("hi") == "hi"


def test_multiple_results_are_not_attributed_to_one_model():
    entry = {"fields": {"x_provider": "p"}}
    node = _node(_res("a", {RESPONSE_METADATA_KEY: entry}), _res("b"))
    assert node._as_message("a\n\nb") == "a\n\nb"
