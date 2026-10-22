"""An agent that runs out of rounds without answering asks the model for a final answer."""
from types import SimpleNamespace

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.nodes.common.capabilities.agent_capable import AgentCapableMixin
from mas.elements.nodes.common.agent import AgentConfig


class _Strategy:
    strategy_name = "react"

    def build_context(self, messages):
        return [ChatMessage(role=Role.SYSTEM, content="system")] + list(messages)


class _EmptyIterator:
    """Stops at once, the way an iterator does when max_steps is exhausted."""

    def __init__(self, messages):
        self.messages = messages
        self.history = []
        self.observations = []

    def __iter__(self):
        return iter(())


class _Agent(AgentCapableMixin[object]):
    def __init__(self, reply=None, fail=False):
        self.reply, self.fail, self.chats = reply, fail, []

    def create_iterator(self, messages, strategy, *, config=None, on_action=None):
        return _EmptyIterator(list(messages))

    def is_streaming(self):
        return False

    def _stream(self, event):
        pass

    def chat(self, messages, tools=None):
        self.chats.append(messages)
        if self.fail:
            raise RuntimeError("model down")
        return SimpleNamespace(content=self.reply)


def _run(agent):
    user = ChatMessage(role=Role.USER, content="What does page X say?")
    return agent.run_agent([user], _Strategy(), config=AgentConfig())


def test_exhausted_rounds_get_a_final_answer():
    agent = _Agent(reply="I found nothing on X in the documents I could read.")
    result = _run(agent)
    assert result["output"] == "I found nothing on X in the documents I could read."
    assert result["success"] is True
    assert result["metadata"]["wrapped_up"] is True
    last = agent.chats[0][-1]
    assert last.role == Role.USER and "Do not call any tool" in last.content
    assert agent.chats[0][0].role == Role.SYSTEM and agent.chats[0][1].content == "What does page X say?"


def test_a_failing_wrap_up_keeps_the_plain_outcome():
    result = _run(_Agent(fail=True))
    assert result["output"] == "Agent completed without producing output"
    assert result["success"] is False
    assert "wrapped_up" not in result["metadata"]


def test_an_empty_wrap_up_keeps_the_plain_outcome():
    result = _run(_Agent(reply="   "))
    assert result["output"] == "Agent completed without producing output"
    assert result["success"] is False
