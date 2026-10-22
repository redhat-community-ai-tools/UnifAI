"""HTTP 429 from an OpenAI-compatible endpoint maps to ``LLMRateLimitError``."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import httpx
import pytest
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.llms.common.exceptions import (
    LLMRateLimitError,
    parse_retry_after,
)
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM, build_http_client

QUOTA_BODY = {
    "error": "quota_exceeded",
    "quota_class": "demo",
    "dimension": "project",
    "budget_tokens": 1000,
    "window": "1h",
}


def _llm(handler, tracing=None, max_retries=2):
    if tracing is None:
        tracing = MagicMock()

        @contextmanager
        def trace_llm(**_kw):
            yield MagicMock()

        tracing.trace_llm = trace_llm
    return OpenAICompatibleLLM(
        base_url="http://llm.test/v1",
        model_name="m",
        tracing=tracing,
        max_retries=max_retries,
        http_client=build_http_client(transport=httpx.MockTransport(handler)),
    )


def _respond_429(headers=None, body=QUOTA_BODY):
    return lambda request: httpx.Response(429, json=body, headers=headers or {})


MESSAGES = [ChatMessage(role=Role.USER, content="hi")]


def _call(llm, streaming):
    if streaming:
        return list(llm.stream(MESSAGES))
    return llm.chat(MESSAGES)


@pytest.mark.parametrize("streaming", [False, True], ids=["chat", "stream"])
class TestRateLimitMapping:
    def test_429_with_retry_after(self, streaming):
        llm = _llm(_respond_429({"Retry-After": "42"}))
        with pytest.raises(LLMRateLimitError) as info:
            _call(llm, streaming)
        err = info.value
        assert err.status_code == 429
        assert err.retry_after == 42
        assert "quota_exceeded" in err.detail
        assert "quota_class=demo" in err.detail
        assert "retry in 42s" in err.user_message()

    def test_429_without_retry_after(self, streaming):
        llm = _llm(_respond_429())
        with pytest.raises(LLMRateLimitError) as info:
            _call(llm, streaming)
        assert info.value.retry_after is None
        assert "retry" not in info.value.user_message().lower()

    def test_429_with_plain_text_body(self, streaming):
        llm = _llm(lambda r: httpx.Response(429, text="slow down"))
        with pytest.raises(LLMRateLimitError) as info:
            _call(llm, streaming)
        assert "slow down" in info.value.detail

    def test_other_status_is_not_mapped(self, streaming):
        llm = _llm(lambda r: httpx.Response(500, json={"error": "boom"}))
        with pytest.raises(Exception) as info:
            _call(llm, streaming)
        assert not isinstance(info.value, LLMRateLimitError)

    def test_trace_is_a_warning_not_an_error(self, streaming):
        gen = MagicMock()
        tracing = MagicMock()

        @contextmanager
        def trace_llm(**_kw):
            yield gen

        tracing.trace_llm = trace_llm
        llm = _llm(_respond_429({"Retry-After": "1"}), tracing)
        with pytest.raises(LLMRateLimitError):
            _call(llm, streaming)
        assert gen.update.call_args.kwargs["level"] == "WARNING"


class TestRetries:
    @staticmethod
    def _counting(status, **kw):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(status, **kw)

        return calls, handler

    @pytest.mark.parametrize("streaming", [False, True], ids=["chat", "stream"])
    def test_429_is_sent_exactly_once_even_with_retries_enabled(self, streaming):
        calls, handler = self._counting(429, json=QUOTA_BODY, headers={"Retry-After": "1"})
        with pytest.raises(LLMRateLimitError):
            _call(_llm(handler, max_retries=2), streaming)
        assert len(calls) == 1

    def test_503_is_retried(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda _s: None)
        calls, handler = self._counting(503, json={"error": "down"})
        with pytest.raises(Exception) as info:
            _call(_llm(handler, max_retries=2), False)
        assert not isinstance(info.value, LLMRateLimitError)
        assert len(calls) == 3


class TestErrorText:
    def test_to_dict_with_delay(self):
        err = LLMRateLimitError("over quota", 30)
        assert err.to_dict() == {
            "type": "rate_limited",
            "message": "Rate limit reached: over quota Please retry in 30s.",
            "retry_after": 30,
        }

    def test_to_dict_without_delay(self):
        d = LLMRateLimitError("over quota").to_dict()
        assert d["retry_after"] is None and "retry" not in d["message"].lower()

    def test_str_is_readable_without_marker(self):
        assert str(LLMRateLimitError("over quota", 5)) == "Rate limit reached: over quota Please retry in 5s."

    def test_parse_retry_after_forms(self):
        assert parse_retry_after("7") == 7
        assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0
        assert parse_retry_after("garbage") is None
        assert parse_retry_after(None) is None


class TestAgentLoopTreatsRateLimitAsNonFatal:
    def test_react_step_is_terminal_rate_limited_without_retry_feedback(self):
        from unittest.mock import Mock

        from mas.elements.nodes.common.agent.primitives import StepType
        from mas.elements.nodes.common.agent.strategies.react import ReActStrategy

        def llm_chat(_ctx, _tools):
            raise LLMRateLimitError("over quota", 12)

        strategy = ReActStrategy(llm_chat=llm_chat, tools=[], parser=Mock())
        messages = [ChatMessage(role=Role.USER, content="hi")]

        steps = strategy.think(messages)

        assert len(steps) == 1
        step = steps[0]
        assert step.type == StepType.ERROR and step.is_terminal
        assert step.metadata["error_type"] == "rate_limited"
        assert step.metadata["recoverable"] is False
        assert step.metadata["retry_after"] == 12
        # No "try a different approach" feedback appended for a call that never ran
        assert len(messages) == 1


class TestStructuredErrorPropagation:
    def test_final_answer_message_carries_structured_error(self):
        from mas.elements.llms.common.chat.message import ERROR_METADATA_KEY
        from mas.elements.nodes.common.workload import AgentResult
        from mas.elements.nodes.final_answer.final_answer import FinalAnswerNode

        err = LLMRateLimitError("over quota", 9)
        node = FinalAnswerNode.__new__(FinalAnswerNode)
        node._collected_results = [
            AgentResult(
                content=str(err), agent_id="a", agent_name="A", success=False,
                error=str(err), execution_metadata={ERROR_METADATA_KEY: err.to_dict()},
            )
        ]
        msg = node._as_message(node._merge_results())
        assert isinstance(msg, ChatMessage)
        assert msg.metadata[ERROR_METADATA_KEY] == err.to_dict()
        assert "[" not in msg.content.split(":")[0]  # readable, no marker prefix
        assert "retry in 9s" in msg.content

    def test_stream_agent_error_event_has_typed_fields(self):
        from mas.elements.nodes.common.capabilities.agent_capable import AgentCapableMixin

        fields = AgentCapableMixin._error_event_fields(LLMRateLimitError("x", 4))
        assert fields == {"error_type": "rate_limited", "retry_after": 4}
        assert AgentCapableMixin._error_event_fields(ValueError("x")) == {}
