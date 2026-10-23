"""retrieve_first: the retriever result is put in front of the user prompt before the model reasons."""
from types import SimpleNamespace
from unittest.mock import Mock

from mas.elements.llms.common.chat.message import Role
from mas.elements.nodes.custom_agent.config import CustomAgentNodeConfig
from mas.elements.nodes.custom_agent.custom_agent import CustomAgentNode


class _Node(CustomAgentNode):
    """The node without its runtime wiring: only what the conversation context reads."""

    workspaces = Mock(get_recent_messages=Mock(return_value=[]))


def _node(retrieve_first, retriever):
    node = _Node.__new__(_Node)
    node.retriever = retriever
    node.retrieve_first = retrieve_first
    node._build_agent_results_context = lambda thread_id: None
    return node


def _context(node):
    return node._build_conversation_context(SimpleNamespace(thread_id="t", content="What is the PO status?"))


def test_retrieve_first_puts_the_context_in_front_of_the_prompt():
    retriever = Mock(retrieve=Mock(return_value="PAGE: Acme renewal PO received"))
    messages = _context(_node(True, retriever))
    retriever.retrieve.assert_called_once_with("What is the PO status?")
    assert messages[-1].role == Role.USER
    assert messages[-1].content == "context: PAGE: Acme renewal PO received\nuser:\nWhat is the PO status?"


def test_default_leaves_retrieval_to_the_model():
    retriever = Mock(retrieve=Mock(return_value="PAGE"))
    messages = _context(_node(False, retriever))
    retriever.retrieve.assert_not_called()
    assert messages[-1].content == "What is the PO status?"


def test_a_retrieval_failure_does_not_fail_the_turn():
    retriever = Mock(retrieve=Mock(side_effect=RuntimeError("rag down")))
    messages = _context(_node(True, retriever))
    assert messages[-1].content == "What is the PO status?"


def test_no_retriever_no_retrieval():
    assert _context(_node(True, None))[-1].content == "What is the PO status?"


def test_config_defaults_to_off():
    assert CustomAgentNodeConfig.model_fields["retrieve_first"].default is False
