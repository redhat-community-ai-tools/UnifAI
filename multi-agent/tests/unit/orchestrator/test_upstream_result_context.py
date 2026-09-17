"""Regression coverage for agent -> orchestrator result handoff."""

from unittest.mock import Mock

import pytest

from mas.elements.nodes.common.workload import AgentResult, Task
from mas.elements.nodes.orchestrator.context import OrchestratorCycle
from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
from mas.graph.models import StepContext
from tests.base.test_helpers import setup_node_with_state


@pytest.mark.unit
class TestUpstreamResultContext:
    def test_new_work_captures_upstream_result_for_its_cycle(self):
        node = OrchestratorNode(llm=Mock())
        setup_node_with_state(node)
        node.set_context(StepContext(uid="orchestrator"))
        task = Task(
            task_id="google-output-task",
            content="continue work",
            thread_id="workflow-thread",
            created_by="google-agent",
            result=AgentResult(
                content="UPSTREAM_CUSTOM_RESULT_123",
                agent_id="google-agent",
                agent_name="Google Agent",
            ),
        )

        node._handle_new_work(task)

        message = node._build_upstream_results_context("workflow-thread")
        assert message is not None
        assert "UPSTREAM_CUSTOM_RESULT_123" in message.content
        assert node._orchestration_cycles["workflow-thread"].has_new_requests

        messages = node._build_context_messages("workflow-thread", "continue work")
        assert any("UPSTREAM_CUSTOM_RESULT_123" in message.content for message in messages)
        assert messages[-1].content == "continue work"

    def test_upstream_result_is_discarded_after_its_cycle(self):
        node = OrchestratorNode(llm=Mock())
        task = Task(
            content="continue work",
            thread_id="workflow-thread",
            result=AgentResult(
                content="UPSTREAM_CUSTOM_RESULT_123",
                agent_id="google-agent",
                agent_name="Google Agent",
            ),
        )
        node._record_upstream_task_result(task)
        node._execute_cycle_inner = Mock()

        node._execute_cycle(OrchestratorCycle(thread_id="workflow-thread"))

        assert node._build_upstream_results_context("workflow-thread") is None

    def test_formats_packet_result_with_provenance(self):
        node = OrchestratorNode(llm=Mock())
        task = Task(
            task_id="google-output-task",
            content="continue work",
            thread_id="workflow-thread",
            parent_task_id="user-task",
            created_by="google-agent",
            result=AgentResult(
                content="UPSTREAM_CUSTOM_RESULT_123",
                agent_id="google-agent",
                agent_name="Google Agent",
                success=True,
            ),
        )

        node._record_upstream_task_result(task)

        message = node._build_upstream_results_context("workflow-thread")

        assert message is not None
        assert message.role.value == "user"
        assert "UPSTREAM_CUSTOM_RESULT_123" in message.content
        assert "source_agent_id: google-agent" in message.content
        assert "source_task_id: google-output-task" in message.content
        assert "parent_task_id: user-task" in message.content

    def test_ignores_duplicate_packet_task_and_tasks_without_results(self):
        node = OrchestratorNode(llm=Mock())
        task = Task(
            task_id="upstream-task",
            content="continue work",
            thread_id="workflow-thread",
            result=AgentResult(
                content="UPSTREAM_CUSTOM_RESULT_123",
                agent_id="google-agent",
                agent_name="Google Agent",
            ),
        )

        node._record_upstream_task_result(task)
        node._record_upstream_task_result(task)
        node._record_upstream_task_result(
            Task(content="plain request", thread_id="workflow-thread")
        )

        message = node._build_upstream_results_context("workflow-thread")

        assert message is not None
        assert message.content.count("BEGIN UPSTREAM RESULT") == 1
