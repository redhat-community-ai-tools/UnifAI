"""Unit tests for the native Anthropic (Claude) LLM element.

Covers catalog registration, config discrimination, message/tool conversion,
response parsing, and factory instantiation. No network calls are made — the
Anthropic client constructor does not hit the API, and response objects are
faked with ``SimpleNamespace``.
"""
from types import SimpleNamespace
from typing import Union, get_args, get_origin

import pytest
from pydantic import TypeAdapter

from mas.core.enums import ResourceCategory
from mas.elements.llms.types import LLMsSpec
from mas.elements.llms.anthropic.config import AnthropicConfig
from mas.elements.llms.anthropic.anthropic import AnthropicLLM
from mas.elements.llms.anthropic.anthropic_factory import AnthropicFactory
from mas.elements.llms.anthropic.identifiers import Identifier
from mas.elements.llms.anthropic.message_converter import AnthropicMessageConverter
from mas.elements.llms.anthropic.tools_converter import AnthropicToolsConverter
from mas.elements.llms.anthropic.spec.spec import AnthropicElementSpec
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.tools.common.tool_definition import ToolDefinition

pytestmark = pytest.mark.unit


def _llmsspec_members():
    union = get_args(LLMsSpec)[0]
    assert get_origin(union) is Union
    return get_args(union)


class TestAnthropicCatalogRegistration:
    def test_anthropic_config_is_registered_in_llmsspec(self):
        assert AnthropicConfig in _llmsspec_members()

    def test_anthropic_config_validates_through_llmsspec(self):
        cfg = TypeAdapter(LLMsSpec).validate_python({
            "type": "anthropic",
            "model_name": "claude-sonnet-4-5",
            "api_key": "sk-test",
        })
        assert isinstance(cfg, AnthropicConfig)
        assert cfg.type == "anthropic"

    def test_spec_metadata_is_well_formed(self):
        assert AnthropicElementSpec.type_key == Identifier.TYPE
        assert AnthropicElementSpec.category == ResourceCategory.LLM
        assert AnthropicElementSpec.config_schema is AnthropicConfig
        assert AnthropicElementSpec.factory_cls is AnthropicFactory
        assert AnthropicElementSpec.validator_cls is not None

    def test_config_defaults_and_bounds(self):
        cfg = AnthropicConfig()
        assert cfg.max_tokens > 0
        with pytest.raises(Exception):
            AnthropicConfig(temperature=5.0)  # outside [0, 1]


class TestAnthropicMessageConverter:
    def test_system_messages_are_extracted_separately(self):
        split = AnthropicMessageConverter.to_anthropic([
            ChatMessage(role=Role.SYSTEM, content="be terse"),
            ChatMessage(role=Role.USER, content="hi"),
        ])
        assert split.system == "be terse"
        assert [m["role"] for m in split.messages] == ["user"]
        assert split.messages[0]["content"][0] == {"type": "text", "text": "hi"}

    def test_assistant_tool_calls_become_tool_use_blocks(self):
        msg = ChatMessage(
            role=Role.ASSISTANT,
            content="calling",
            tool_calls=[ToolCall(name="search", args={"q": "x"}, tool_call_id="tu_1")],
        )
        blocks = AnthropicMessageConverter.to_anthropic([msg]).messages[0]["content"]
        assert {"type": "text", "text": "calling"} in blocks
        assert {
            "type": "tool_use", "id": "tu_1", "name": "search", "input": {"q": "x"},
        } in blocks

    def test_tool_results_and_consecutive_user_roles_are_coalesced(self):
        # An assistant turn with two parallel tool calls, followed by two tool
        # results, must collapse into a single alternating user turn.
        msgs = [
            ChatMessage(role=Role.USER, content="go"),
            ChatMessage(
                role=Role.ASSISTANT, content="",
                tool_calls=[
                    ToolCall(name="a", args={}, tool_call_id="t1"),
                    ToolCall(name="b", args={}, tool_call_id="t2"),
                ],
            ),
            ChatMessage(role=Role.TOOL, content="r1", tool_call_id="t1"),
            ChatMessage(role=Role.TOOL, content="r2", tool_call_id="t2"),
        ]
        out = AnthropicMessageConverter.to_anthropic(msgs).messages
        roles = [m["role"] for m in out]
        assert roles == ["user", "assistant", "user"]  # strictly alternating
        tool_results = out[2]["content"]
        assert len(tool_results) == 2
        assert {b["tool_use_id"] for b in tool_results} == {"t1", "t2"}
        assert all(b["type"] == "tool_result" for b in tool_results)

    def test_message_from_blocks_parses_text_and_tool_use(self):
        blocks = [
            SimpleNamespace(type="text", text="hello "),
            SimpleNamespace(type="text", text="world"),
            SimpleNamespace(type="tool_use", id="tu_9", name="lookup", input={"k": 1}),
        ]
        msg = AnthropicMessageConverter.message_from_blocks(blocks)
        assert msg.role == Role.ASSISTANT
        assert msg.content == "hello world"
        assert msg.tool_calls is not None and len(msg.tool_calls) == 1
        tc = msg.tool_calls[0]
        assert (tc.name, tc.tool_call_id, tc.args) == ("lookup", "tu_9", {"k": 1})

    def test_message_from_blocks_without_tools_has_no_tool_calls(self):
        msg = AnthropicMessageConverter.message_from_blocks(
            [SimpleNamespace(type="text", text="just text")]
        )
        assert msg.tool_calls is None


class TestAnthropicToolsConverter:
    def test_none_when_no_tools(self):
        assert AnthropicToolsConverter.to_anthropic(None) is None
        assert AnthropicToolsConverter.to_anthropic([]) is None

    def test_tool_definition_maps_to_input_schema(self):
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        tools = AnthropicToolsConverter.to_anthropic([
            ToolDefinition(name="search", description="find things", parameters=schema),
        ])
        assert tools == [{
            "name": "search",
            "description": "find things",
            "input_schema": schema,
        }]


class TestAnthropicFactory:
    def test_factory_accepts_only_anthropic_type(self):
        factory = AnthropicFactory()
        cfg = AnthropicConfig(api_key="sk-test")
        assert factory.accepts(cfg, "anthropic") is True
        assert factory.accepts(cfg, "openai") is False

    def test_factory_creates_llm_without_network(self):
        # The Anthropic client constructor does not perform any I/O.
        llm = AnthropicFactory().create(AnthropicConfig(api_key="sk-test"))
        assert isinstance(llm, AnthropicLLM)
        assert llm.name == "anthropic"

    def test_bind_tools_returns_new_instance(self):
        llm = AnthropicFactory().create(AnthropicConfig(api_key="sk-test"))
        bound = llm.bind_tools([ToolDefinition(name="t", description="d")])
        assert bound is not llm
        assert isinstance(bound, AnthropicLLM)
