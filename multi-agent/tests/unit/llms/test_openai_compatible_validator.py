"""Unit tests for OpenAI-compatible LLM validator.

Covers the fallback logic when ``GET /v1/models/{id}`` is unsupported
by the upstream gateway (404, 405, 501) and the chat-completion probe
that replaces the legacy completions probe.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
from openai import NotFoundError, APIStatusError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from pydantic import HttpUrl

from mas.elements.common.validator import ValidationCode, ValidationContext
from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig
from mas.elements.llms.openai_compatible.validator import (
    OpenAICompatibleLLMValidator,
)


def _config(**overrides: Any) -> OpenAICompatibleConfig:
    data: dict[str, Any] = {
        "base_url": HttpUrl("http://llm.example:8000/v1"),
        "model_name": "test-model",
        "api_key": "sk-test",
    }
    data.update(overrides)
    return OpenAICompatibleConfig(**data)


def _context(**overrides: Any) -> ValidationContext:
    data: dict[str, Any] = {"timeout_seconds": 5.0}
    data.update(overrides)
    return ValidationContext(**data)


def _fake_chat_completion() -> ChatCompletion:
    """Minimal ChatCompletion object returned by the probe."""
    return ChatCompletion(
        id="val-probe",
        object="chat.completion",
        created=0,
        model="test-model",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="hi"),
                finish_reason="stop",
            )
        ],
    )


def _make_response(status_code: int, body: dict | None = None) -> httpx.Response:
    """Build an httpx.Response with a request attached (required by openai)."""
    request = httpx.Request("GET", "http://llm.example:8000/v1/models/test-model")
    if body is None:
        body = {"error": {"message": f"HTTP {status_code}"}}
    resp = httpx.Response(status_code, json=body, request=request)
    return resp


def _not_found_error() -> NotFoundError:
    """Simulate a 404 from ``client.models.retrieve()``."""
    resp = _make_response(404, {"error": {"message": "not found"}})
    return NotFoundError(
        message="not found",
        response=resp,
        body={"error": {"message": "not found"}},
    )


def _api_status_error(status_code: int) -> APIStatusError:
    """Simulate an arbitrary HTTP error from ``client.models.retrieve()``."""
    resp = _make_response(status_code)
    return APIStatusError(
        message=f"HTTP {status_code}",
        response=resp,
        body={"error": {"message": f"HTTP {status_code}"}},
    )


class TestModelRetrieveFallback:
    """Validate that unsupported /v1/models/{id} falls back correctly."""

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_models_retrieve_succeeds(self, mock_openai_cls):
        """Happy path: ``models.retrieve()`` works, no fallback needed."""
        client = MagicMock()
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert report.is_valid
        client.models.retrieve.assert_called_once_with("test-model")
        client.chat.completions.create.assert_not_called()

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_404_falls_back_to_chat_completion(self, mock_openai_cls):
        """404 from ``models.retrieve()`` triggers chat completion probe."""
        client = MagicMock()
        client.models.retrieve.side_effect = _not_found_error()
        client.chat.completions.create.return_value = _fake_chat_completion()
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert report.is_valid
        client.chat.completions.create.assert_called_once()
        call_kwargs = client.chat.completions.create.call_args
        assert call_kwargs[1]["model"] == "test-model"
        assert call_kwargs[1]["max_completion_tokens"] == 1

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_405_falls_back_to_chat_completion(self, mock_openai_cls):
        """405 (Method Not Allowed) from ``models.retrieve()`` triggers
        the same chat completion fallback.  This covers API gateways
        that support ``GET /v1/models`` (list) but return 405 on
        ``GET /v1/models/{id}`` (retrieve single).
        """
        client = MagicMock()
        client.models.retrieve.side_effect = _api_status_error(405)
        client.chat.completions.create.return_value = _fake_chat_completion()
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert report.is_valid
        client.models.retrieve.assert_called_once_with("test-model")
        client.chat.completions.create.assert_called_once()
        assert any(m.code == "MODEL_AVAILABLE" for m in report.messages)

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_501_falls_back_to_chat_completion(self, mock_openai_cls):
        """501 (Not Implemented) also triggers the fallback."""
        client = MagicMock()
        client.models.retrieve.side_effect = _api_status_error(501)
        client.chat.completions.create.return_value = _fake_chat_completion()
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert report.is_valid
        client.models.retrieve.assert_called_once_with("test-model")
        client.chat.completions.create.assert_called_once()

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_500_is_not_swallowed(self, mock_openai_cls):
        """A generic 500 from ``models.retrieve()`` should NOT trigger
        the fallback; it must propagate to the outer error handler."""
        client = MagicMock()
        client.models.retrieve.side_effect = _api_status_error(500)
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert not report.is_valid
        assert any(
            m.code == ValidationCode.NETWORK_ERROR.value for m in report.messages
        )
        client.chat.completions.create.assert_not_called()

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_502_is_not_swallowed(self, mock_openai_cls):
        """502 (Bad Gateway) must not be silently retried."""
        client = MagicMock()
        client.models.retrieve.side_effect = _api_status_error(502)
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert not report.is_valid
        client.chat.completions.create.assert_not_called()


class TestChatCompletionProbe:
    """Validate the chat completion probe uses the correct API shape."""

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_probe_sends_chat_not_legacy(self, mock_openai_cls):
        """The probe must call ``chat.completions.create()``, not the
        legacy ``completions.create()`` endpoint."""
        client = MagicMock()
        client.models.retrieve.side_effect = _not_found_error()
        client.chat.completions.create.return_value = _fake_chat_completion()
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        report = validator.validate(_config(), _context())

        assert report.is_valid
        client.chat.completions.create.assert_called_once()
        # Legacy endpoint must NOT be called
        client.completions.create.assert_not_called()

    @patch("mas.elements.llms.openai_compatible.validator.OpenAI")
    def test_probe_sends_complete_request(self, mock_openai_cls):
        """Chat completion probe must send model, messages, and token limit."""
        client = MagicMock()
        client.models.retrieve.side_effect = _not_found_error()
        client.chat.completions.create.return_value = _fake_chat_completion()
        mock_openai_cls.return_value = client

        validator = OpenAICompatibleLLMValidator()
        validator.validate(_config(), _context())

        call_kwargs = client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
        assert call_kwargs["max_completion_tokens"] == 1
