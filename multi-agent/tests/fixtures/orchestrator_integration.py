"""
SOLID Integration fixtures for orchestrator testing.

This module provides clean, reusable, and well-designed fixtures for integration testing
of the orchestrator system. All fixtures follow SOLID principles and are designed to work
together seamlessly.

Key Design Principles:
- Single Responsibility: Each fixture has one clear purpose
- Open/Closed: Easy to extend without modification  
- Liskov Substitution: Fixtures can be safely substituted
- Interface Segregation: No forced dependencies on unused functionality
- Dependency Inversion: Depend on abstractions, not concretions
"""

import uuid
from typing import List, Dict, Any, Optional, Iterator, Union
from dataclasses import dataclass, field
from unittest.mock import Mock
import pytest

from mas.elements.llms.common.base_llm import BaseLLM
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.tools.common.tool_definition import ToolDefinition
from mas.elements.nodes.common.workload import Task, WorkPlan, WorkItem
from mas.core.iem.packets import TaskPacket
from mas.core.iem.models import ElementAddress


# Legacy class for backward compatibility with other test files
@dataclass
class OrchestrationScenario:
    """
    Legacy orchestration scenario class for backward compatibility.
    
    This class exists to support other integration test files that may
    still be importing it. New tests should use the SOLID fixtures directly.
    """
    name: str = "default_scenario"
    description: str = "Default orchestration scenario"
    
    def setup_llm_responses(self, predictable_llm: 'PredictableLLM') -> None:
        """Set up basic LLM responses for orchestration."""
        # Add basic work plan creation response
        predictable_llm.add_tool_call_response(
            tool_name="workplan.create_or_update",
            arguments={
                "summary": "Basic work plan",
                "items": [{
                    "id": "task_1",
                    "title": "Basic Task",
                    "description": "A basic task for testing",
                    "dependencies": [],
                    "kind": "remote"
                }]
            },
            content="Created basic work plan"
        )


class PredictableLLM(BaseLLM):
    """
    Deterministic LLM controller for reliable integration testing.
    
    Provides predictable responses and tracks all interactions for verification.
    Implements the full BaseLLM interface to work with the real system.
    """
    
    def __init__(self, shared_state=None):
        if shared_state is None:
            # Create new shared state for this instance
            self._shared_state = {
                'responses': [],
                'call_count': 0,
                'call_history': []
            }
        else:
            # Use existing shared state (for bound instances)
            self._shared_state = shared_state
    
    @property
    def responses(self):
        return self._shared_state['responses']
    
    @responses.setter
    def responses(self, value):
        self._shared_state['responses'] = value
    
    @property
    def call_count(self):
        return self._shared_state['call_count']
    
    @call_count.setter
    def call_count(self, value):
        self._shared_state['call_count'] = value
    
    @property
    def call_history(self):
        return self._shared_state['call_history']
    
    @call_history.setter
    def call_history(self, value):
        self._shared_state['call_history'] = value
    
    def add_response(self, content: str, tool_calls: List[ToolCall] = None):
        """Add a text response that will be returned on the next LLM call."""
        response = ChatMessage(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tool_calls or []
        )
        self.responses.append(response)
    
    def add_tool_call_response(self, tool_name: str, arguments: Dict[str, Any], content: str = ""):
        """Add a tool call response that will be returned on the next LLM call."""
        tool_call = ToolCall(
            name=tool_name,
            args=arguments,
            tool_call_id=f"call_{uuid.uuid4().hex[:8]}"
        )
        response = ChatMessage(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=[tool_call]
        )
        self.responses.append(response)
    
    def chat(self, messages: List[ChatMessage], **kwargs) -> ChatMessage:
        """Return the next pre-configured response and track the call."""
        self.call_count += 1
        self.call_history.append({
            'messages': messages,
            'kwargs': kwargs
        })
        
        if self.responses:
            return self.responses.pop(0)
        else:
            # Default response if no responses configured
            return ChatMessage(
                role=Role.ASSISTANT,
                content="I understand the request and will proceed accordingly."
            )
    
    def stream(self, messages: List[ChatMessage], **call_params: Any) -> Iterator[Union[str, ChatMessage]]:
        """Stream implementation - just yields the final response."""
        response = self.chat(messages)
        yield response.content
        yield response
    
    def bind_tools(self, tools: List[ToolDefinition]) -> "PredictableLLM":
        """Return a copy of the LLM with tools bound that shares call tracking."""
        return PredictableLLM(shared_state=self._shared_state)
    
    @property 
    def name(self) -> str:
        """Return the LLM name for logging/debug."""
        return "predictable_test_llm"
    
    def reset(self):
        """Reset the LLM state for a fresh test."""
        self.responses.clear()
        self.call_count = 0
        self.call_history.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of LLM interactions for test verification."""
        return {
            'call_count': self.call_count,
            'remaining_responses': len(self.responses),
            'call_history': self.call_history
        }


@dataclass
class ExecutionTracker:
    """
    Simple execution tracker for monitoring orchestrator behavior.
    
    Tracks key metrics and provides verification methods for integration tests.
    """
    workspace_facts: int = 0
    workspace_variables: int = 0 
    work_plan_created: bool = False
    llm_calls: int = 0
    errors: List[str] = field(default_factory=list)
    
    def track_workspace_fact(self, fact: str):
        """Track a workspace fact being added."""
        self.workspace_facts += 1
    
    def track_workspace_variable(self, key: str, value: Any):
        """Track a workspace variable being set."""
        self.workspace_variables += 1
    
    def track_work_plan_creation(self, plan: WorkPlan):
        """Track work plan creation."""
        self.work_plan_created = True
    
    def track_llm_call(self):
        """Track an LLM call."""
        self.llm_calls += 1
    
    def track_error(self, error: str):
        """Track an error occurrence."""
        self.errors.append(error)
    
    def verify_basic_execution(self) -> bool:
        """Verify basic execution occurred without errors."""
        return len(self.errors) == 0 and self.llm_calls > 0
    
    def verify_workspace_operations(self) -> bool:
        """Verify workspace operations occurred."""
        return self.workspace_facts > 0 or self.workspace_variables > 0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary for verification."""
        return {
            'workspace_facts': self.workspace_facts,
            'workspace_variables': self.workspace_variables,
            'work_plan_created': self.work_plan_created,
            'llm_calls': self.llm_calls,
            'errors': len(self.errors),
            'success': len(self.errors) == 0
        }


def create_step_context_local(uid: str, adjacent_nodes: List[str] = None):
    """
    Create a StepContext for testing (local version to avoid circular imports).
    
    Args:
        uid: Unique identifier for the node
        adjacent_nodes: List of adjacent node UIDs
        
    Returns:
        StepContext instance for testing
    """
    from mas.graph.models import StepContext
    from mas.graph.models import AdjacentNodes
    from mas.elements.common.card import ElementCard
    from mas.core.enums import ResourceCategory
    from mas.blueprints.models.blueprint import StepMeta
    
    if adjacent_nodes is None:
        adjacent_nodes = []
    
    # Create adjacency data structure
    adjacent_nodes_dict = {}
    for node_uid in adjacent_nodes:
        card = ElementCard(
            uid=node_uid,
            category=ResourceCategory.NODE,
            type_key="test_node",
            name=node_uid,
            description=f"Test node {node_uid}",
            capabilities=[],
            skills=[],
            configuration={},
        )
        adjacent_nodes_dict[node_uid] = card
    
    # Create clean Pydantic model
    adjacent_nodes_model = AdjacentNodes.from_dict(adjacent_nodes_dict)
    
    return StepContext(
        uid=uid,
        metadata=StepMeta(display_name=uid),
        adjacent_nodes=adjacent_nodes_model,
        branches={}
    )


def create_planning_scenario(predictable_llm: PredictableLLM, task_content: str) -> None:
    """
    Set up a predictable planning scenario for orchestrator testing.
    
    Creates typical LLM responses for planning phase including work plan creation.
    """
    # Add work plan creation response
    predictable_llm.add_tool_call_response(
        tool_name="workplan.create_or_update",
        arguments={
            "summary": f"Work plan for: {task_content}",
            "items": [
                {
                    "id": "item_1",
                    "title": "Analyze Sales Data",
                    "description": "Analyze the Q3 sales data to identify trends and key metrics",
                    "dependencies": [],
                    "kind": "remote"
                },
                {
                    "id": "item_2", 
                    "title": "Create Summary Report",
                    "description": "Create comprehensive summary report based on analysis",
                    "dependencies": ["item_1"],
                    "kind": "remote"
                }
            ]
        },
        content="I've created a work plan to handle this request."
    )


def create_synthesis_scenario(predictable_llm: PredictableLLM) -> None:
    """
    Set up a predictable synthesis scenario for orchestrator testing.
    
    Creates typical LLM responses for synthesis phase.
    """
    predictable_llm.add_response(
        content="I have successfully coordinated the work. The Q3 sales analysis is complete and the summary report has been generated."
    )


def create_task_packet(task: Task, orchestrator_uid: str = "test_orchestrator") -> TaskPacket:
    """
    Create a proper IEM TaskPacket from a Task object.
    
    The orchestrator's IEM messenger expects TaskPacket objects with proper src/dst addressing,
    not raw Task objects.
    """
    return TaskPacket.create(
        src=ElementAddress(uid="user"),
        dst=ElementAddress(uid=orchestrator_uid),
        task=task
    )


# Fixtures for pytest
@pytest.fixture
def predictable_llm():
    """Provide a deterministic LLM controller for testing."""
    return PredictableLLM()


@pytest.fixture
def execution_tracker():
    """Provide an execution tracker for monitoring orchestrator behavior."""
    return ExecutionTracker()


@pytest.fixture
def orchestrator_integration_state(state_view):
    """
    Provide a state configured for orchestrator integration testing.
    
    Simply returns the state_view as it already has the necessary channels configured.
    """
    return state_view


@pytest.fixture
def orchestrator_workspace_service(orchestrator_integration_state):
    """Provide a workspace service bound to the integration state."""
    from mas.elements.nodes.common.workload import UnifiedWorkloadService, StateBoundStorage
    storage = StateBoundStorage(orchestrator_integration_state)
    return UnifiedWorkloadService(storage)


@pytest.fixture
def integration_orchestrator(predictable_llm, orchestrator_integration_state):
    """Provide a fully configured orchestrator for integration testing."""
    from mas.elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
    
    orchestrator = OrchestratorNode(llm=predictable_llm)
    
    # Set up context and state
    step_context = create_step_context_local(
        uid="test_orchestrator", 
        adjacent_nodes=["worker_1", "worker_2"]
    )
    orchestrator.set_context(step_context)
    orchestrator._state = orchestrator_integration_state
    
    return orchestrator


@pytest.fixture
def integration_task_factory():
    """Provide a factory for creating tasks for integration testing."""
    def create_task(content: str, thread_id: str = None, **kwargs) -> Task:
        """Create a task for integration testing."""
        return Task(
            content=content,
            thread_id=thread_id or f"test_thread_{uuid.uuid4().hex[:8]}",
            should_respond=False,
            created_by="integration_test",
            **kwargs
        )
    return create_task


@pytest.fixture
def planning_scenario_helper():
    """Provide helper for setting up planning scenarios."""
    return create_planning_scenario


@pytest.fixture
def synthesis_scenario_helper():
    """Provide helper for setting up synthesis scenarios."""
    return create_synthesis_scenario


@pytest.fixture
def task_packet_helper():
    """Provide helper for creating task packets."""
    return create_task_packet
