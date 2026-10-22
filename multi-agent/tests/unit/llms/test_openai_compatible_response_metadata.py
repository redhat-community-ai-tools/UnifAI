"""Response-metadata passthrough for the openai_compatible LLM (mocked client)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from mas.elements.llms.common.chat.message import (
    RESPONSE_METADATA_KEY,
    ChatMessage,
    Role,
)
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM

LOOKUP = "http://gw/v1/routing-decisions/{response_id}"


def _llm(lookup=None) -> OpenAICompatibleLLM:
    llm = OpenAICompatibleLLM(
        base_url="http://localhost:1/v1",
        model_name="m",
        tracing=MagicMock(),
        metadata_lookup_url=lookup,
    )
    llm._client = MagicMock()
    return llm


def _completion(**extra) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "resp-1",
        "object": "chat.completion",
        "created": 1,
        "model": "served-model",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "hello"},
        }],
        **extra,
    })


def _chunk(content=None, finish=None, **extra) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate({
        "id": "resp-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "served-model",
        "choices": [{
            "index": 0,
            "finish_reason": finish,
            "delta": {"content": content} if content is not None else {},
        }],
        **extra,
    })


USER = [ChatMessage(role=Role.USER, content="hi")]


def test_chat_passes_extra_fields_through_unrenamed():
    llm = _llm()
    llm._client.chat.completions.create.return_value = _completion(x_provider="vllm-a")
    msg = llm.chat(USER)
    entry = msg.metadata[RESPONSE_METADATA_KEY]
    assert entry["fields"] == {"x_provider": "vllm-a"}
    assert entry["response_id"] == "resp-1"
    assert entry["model"] == "served-model"
    assert "lookup_url" not in entry and "routing" not in entry
    assert msg.content == "hello"


def test_chat_without_metadata_is_unchanged():
    llm = _llm()
    llm._client.chat.completions.create.return_value = _completion()
    msg = llm.chat(USER)
    assert msg.metadata == {}
    assert msg.content == "hello"


def test_stream_passes_extra_fields_and_emits_final_message():
    llm = _llm(LOOKUP)
    llm._client.chat.completions.create.return_value = iter([
        _chunk("hel"),
        _chunk("lo", x_provider="vllm-a"),
        _chunk(finish="stop"),
    ])
    out = list(llm.stream(USER))
    assert out[:2] == ["hel", "lo"]
    final = out[-1]
    assert isinstance(final, ChatMessage)
    assert final.content == "hello"
    entry = final.metadata[RESPONSE_METADATA_KEY]
    assert entry["fields"] == {"x_provider": "vllm-a"}


def test_stream_without_metadata_yields_only_text():
    llm = _llm()
    llm._client.chat.completions.create.return_value = iter([
        _chunk("hel"), _chunk("lo"), _chunk(finish="stop"),
    ])
    assert list(llm.stream(USER)) == ["hel", "lo"]


def test_stream_tool_call_message_keeps_metadata():
    llm = _llm()
    tc_chunk = ChatCompletionChunk.model_validate({
        "id": "resp-2", "object": "chat.completion.chunk", "created": 1, "model": "m",
        "x_provider": "p",
        "choices": [{"index": 0, "finish_reason": None, "delta": {"tool_calls": [{
            "index": 0, "id": "c1", "type": "function",
            "function": {"name": "t", "arguments": "{}"},
        }]}}],
    })
    llm._client.chat.completions.create.return_value = iter([tc_chunk])
    final = list(llm.stream(USER))[-1]
    assert final.tool_calls[0].name == "t"
    assert final.metadata[RESPONSE_METADATA_KEY]["fields"] == {"x_provider": "p"}


def test_config_and_factory_carry_lookup_url():
    from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig
    from mas.elements.llms.openai_compatible.openai_compatible_factory import (
        OpenAICompatibleFactory,
    )
    cfg = OpenAICompatibleConfig(
        model_name="m", base_url="http://localhost:1/v1", metadata_lookup_url=LOOKUP,
    )
    deps = SimpleNamespace(tracing_service=MagicMock())
    llm = OpenAICompatibleFactory().create(cfg, deps=deps)
    assert llm._metadata_lookup_url == LOOKUP
    assert OpenAICompatibleConfig(model_name="m", base_url="http://x/v1").metadata_lookup_url is None


def test_langchain_adapter_does_not_duplicate_text_for_metadata_only_message():
    from mas.elements.llms.common.langchain_adapter import BaseLLMChatModelAdapter

    fake = MagicMock()
    fake.name = "fake"
    fake.stream.return_value = iter([
        "hel", "lo",
        ChatMessage(role=Role.ASSISTANT, content="hello",
                    metadata={RESPONSE_METADATA_KEY: {"fields": {"x": 1}}}),
    ])
    chunks = list(BaseLLMChatModelAdapter(llm=fake)._stream([]))
    assert "".join(c.message.content for c in chunks) == "hello"
