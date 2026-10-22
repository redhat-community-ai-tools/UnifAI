"""Tool-call delta aggregation for streamed Chat Completions and Responses events."""

from types import SimpleNamespace

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall, ChoiceDeltaToolCallFunction

from mas.elements.llms.common.chat.tool_arguments import ARGUMENTS_ERROR_KEY
from mas.elements.llms.openai.responses_stream_aggregator import ResponsesStreamAggregator
from mas.elements.llms.openai_compatible.stream_aggregator import StreamToolCallAggregator


def _d(index, id=None, name=None, args=None):
    return ChoiceDeltaToolCall(
        index=index, id=id, type="function" if id else None,
        function=ChoiceDeltaToolCallFunction(name=name, arguments=args),
    )


def _build(chunks):
    agg = StreamToolCallAggregator()
    for c in chunks:
        agg.absorb(c)
    return agg.build()


def test_two_calls_distinct_indexes():
    calls = _build([
        [_d(0, "a", "f", "")], [_d(0, args='{"x":')], [_d(0, args="1}")],
        [_d(1, "b", "g", "")], [_d(1, args='{"y":2}')],
    ])
    assert [(c.tool_call_id, c.name, c.args) for c in calls] == [
        ("a", "f", {"x": 1}), ("b", "g", {"y": 2})]


def test_two_calls_same_index_different_ids():
    calls = _build([
        [_d(0, "a", "f", '{"x":1}')],
        [_d(0, "b", "g", '{"y":2}')],
    ])
    assert [(c.tool_call_id, c.name, c.args) for c in calls] == [
        ("a", "f", {"x": 1}), ("b", "g", {"y": 2})]


def test_same_index_new_name_without_id_after_complete_args():
    calls = _build([
        [_d(0, "a", "f", '{"x":1}')],
        [_d(0, name="g", args='{"y":2}')],
    ])
    assert [(c.name, c.args) for c in calls] == [("f", {"x": 1}), ("g", {"y": 2})]


def test_many_fragments_id_only_on_first():
    frags = ['{"que', 'ry": "he', 'llo wor', 'ld", "n"', ': 3}']
    calls = _build([[_d(0, "a", "search", "")]] + [[_d(0, args=f)] for f in frags])
    assert len(calls) == 1
    assert calls[0].args == {"query": "hello world", "n": 3}
    assert calls[0].tool_call_id == "a"


def test_empty_arguments():
    for chunks in ([[_d(0, "a", "f", "")]], [[_d(0, "a", "f")]], [[_d(0, "a", "f", "{}")]]):
        calls = _build(chunks)
        assert len(calls) == 1 and calls[0].args == {}


def test_interleaved_fragments_by_index():
    calls = _build([
        [_d(0, "a", "f", '{"x":')], [_d(1, "b", "g", '{"y":')],
        [_d(0, args="1}")], [_d(1, args="2}")],
    ])
    assert [(c.tool_call_id, c.args) for c in calls] == [("a", {"x": 1}), ("b", {"y": 2})]


def test_concatenated_objects_without_ids_are_split():
    calls = _build([[_d(0, name="f", args='{"x":1}{"x":2}')]])
    assert [c.args for c in calls] == [{"x": 1}, {"x": 2}]
    assert len({c.tool_call_id for c in calls}) == 2 and all(c.tool_call_id for c in calls)


def test_invalid_json_does_not_raise():
    calls = _build([[_d(0, "a", "f", '{"x": ')]])
    assert len(calls) == 1
    assert ARGUMENTS_ERROR_KEY in calls[0].args


def test_concatenated_objects_with_id_not_split_but_reported():
    calls = _build([[_d(0, "a", "f", '{"x":1}{"x":2}')]])
    assert len(calls) == 1 and ARGUMENTS_ERROR_KEY in calls[0].args


def test_responses_aggregator_two_calls_and_bad_args():
    agg = ResponsesStreamAggregator()
    for i, args in (("i1", '{"x":1}'), ("i2", '{"y": ')):
        agg.process(SimpleNamespace(type="response.function_call_arguments.delta", item_id=i, delta=args))
        agg.process(SimpleNamespace(
            type="response.output_item.done",
            item=SimpleNamespace(type="function_call", id=i, call_id="c" + i, name="f" + i, arguments=args),
        ))
    calls = agg.build()
    assert calls[0].args == {"x": 1}
    assert ARGUMENTS_ERROR_KEY in calls[1].args
