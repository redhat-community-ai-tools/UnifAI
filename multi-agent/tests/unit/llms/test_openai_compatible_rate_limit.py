"""HTTP 429 from an OpenAI-compatible endpoint maps to ``LLMRateLimitError``."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import httpx
import pytest
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.llms.common.exceptions import (
    LLMRateLimitError,
    parse_rate_limit_marker,
    parse_retry_after,
)
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM

QUOTA_BODY = {
    "error": "quota_exceeded",
    "quota_class": "demo",
    "dimension": "project",
    "budget_tokens": 1000,
    "window": "1h",
}


def _llm(handler, tracing=None):
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
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
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


class TestErrorText:
    def test_marker_roundtrip_with_delay(self):
        text = str(LLMRateLimitError("over quota", 30))
        msg, retry = parse_rate_limit_marker(text)
        assert retry == 30
        assert "over quota" in msg

    def test_marker_roundtrip_without_delay(self):
        msg, retry = parse_rate_limit_marker(str(LLMRateLimitError("over quota")))
        assert retry is None and "over quota" in msg

    def test_plain_text_has_no_marker(self):
        assert parse_rate_limit_marker("Error processing task: x") is None

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
        assert parse_rate_limit_marker(str(step.data)) is not None
        # No "try a different approach" feedback appended for a call that never ran
        assert len(messages) == 1
