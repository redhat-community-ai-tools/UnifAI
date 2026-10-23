"""A recoverable error step (e.g. an empty final answer after a tool result) does not end the turn."""
from types import SimpleNamespace

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.nodes.common.agent import AgentConfig
from mas.elements.nodes.common.agent.primitives import AgentFinish, AgentStep, StepType
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.capabilities.agent_capable import AgentCapableMixin


def _error(recoverable):
    return AgentStep(StepType.ERROR, RuntimeError("Reasoning too short (0 chars, min 10)"),
                     metadata={"recoverable": recoverable})


def _react(step_count=1, max_steps=15):
    strategy = object.__new__(ReActStrategy)
    strategy.max_steps, strategy._step_count = max_steps, step_count
    return strategy


def test_the_strategy_continues_after_a_recoverable_error():
    assert _react().should_continue([_error(True)]) is True


def test_the_strategy_stops_after_an_unrecoverable_error():
    assert _react().should_continue([_error(False)]) is False


def test_the_strategy_stops_after_three_recoverable_errors_in_a_row():
    assert _react().should_continue([_error(True)] * 3) is False


def test_the_strategy_stops_on_a_finish():
    finish = AgentStep(StepType.FINISH, AgentFinish(output="done", reasoning="r"))
    assert _react().should_continue([finish]) is False


class _Strategy:
    strategy_name = "react"

    def build_context(self, messages):
        return [ChatMessage(role=Role.SYSTEM, content="system")] + list(messages)


class _Iterator:
    def __init__(self, steps):
        self.steps, self.history, self.observations, self.messages = steps, [], [], []

    def __iter__(self):
        return iter(self.steps)


class _Agent(AgentCapableMixin[object]):
    def __init__(self, steps, wrap_reply=None):
        self.steps, self.wrap_reply = steps, wrap_reply

    def create_iterator(self, messages, strategy, *, config=None, on_action=None):
        return _Iterator(self.steps)

    def is_streaming(self):
        return False

    def _stream(self, event):
        pass

    def chat(self, messages, tools=None):
        return SimpleNamespace(content=self.wrap_reply)


def _run(agent):
    return agent.run_agent([ChatMessage(role=Role.USER, content="q")], _Strategy(), config=AgentConfig())


def test_an_answer_after_a_recoverable_error_is_the_result_without_an_error():
    finish = AgentStep(StepType.FINISH, AgentFinish(output="The PO was received.", reasoning="r"))
    result = _run(_Agent([_error(True), finish]))
    assert result["output"] == "The PO was received."
    assert result["success"] is True
    assert result["error"] is None


def test_recoverable_errors_that_ran_out_get_a_wrap_up_answer():
    result = _run(_Agent([_error(True)] * 3, wrap_reply="From what I read: the PO is pending."))
    assert result["output"] == "From what I read: the PO is pending."
    assert result["success"] is True
    assert result["error"] is None
    assert result["metadata"]["wrapped_up"] is True


def test_an_unrecoverable_error_is_not_wrapped_up():
    result = _run(_Agent([_error(False)], wrap_reply="should not be asked"))
    assert result["output"] is None
    assert result["success"] is False
    assert "Reasoning too short" in result["error"]
