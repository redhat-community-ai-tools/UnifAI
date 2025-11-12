"""
Global test configuration and shared fixtures.

This module imports ALL fixtures from the organized structure and provides
pytest configuration.

ALL TESTS MUST USE THE NEW ARCHITECTURE:
- Inherit from base test classes (BaseNodeTest, BaseOrchestratorTest, etc.)
- Use factories for object creation (NodeFactory, TaskFactory, etc.)
- Use organized fixtures from tests/fixtures/
- Use current workload API (UnifiedWorkloadService, not deprecated WorkPlanService)
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any

# Add the multi-agent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ============================================================================
# IMPORT ALL FIXTURES FROM ORGANIZED STRUCTURE
# ============================================================================

# Common fixtures - state, context, LLM, tools
from tests.fixtures.common.state_fixtures import graph_state, state_view, readonly_state_view
from tests.fixtures.common.context_fixtures import (
    step_context, step_context_with_adjacency, orchestrator_step_context,
    orchestrator_step_context_with_many_nodes, orchestrator_step_context_isolated
)
from tests.fixtures.common.llm_fixtures import (
    mock_llm, mock_llm_chat, mock_llm_provider, predictable_llm
)
from tests.fixtures.common.tool_fixtures import (
    mock_tools, basic_test_tools, mock_domain_tools, calculator_tool, 
    search_tool, basic_mock_tools, react_demo_tools
)

# Workload fixtures - tasks, workplans, workspaces
from tests.fixtures.workload.task_fixtures import (
    sample_task, sample_response_task, sample_ambiguous_response_task,
    integration_task_factory
)
from tests.fixtures.workload.workplan_fixtures import (
    sample_work_item, sample_work_item_with_result, sample_work_plan,
    complex_work_plan, empty_work_plan, large_work_plan
)
from tests.fixtures.workload.workspace_fixtures import (
    mock_workspace, mock_workload_service, workspace_service,
    workspace_service_with_data, orchestrator_workspace_service
)

# Node fixtures - node-specific utilities
from tests.fixtures.nodes.base_node_fixtures import (
    mock_tool_executor_manager, mock_agent_action_executor, sample_config
)

# Import core types
from elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from elements.tools.common.base_tool import BaseTool
from elements.nodes.common.agent.primitives import AgentAction, AgentObservation, AgentFinish
from elements.nodes.common.agent.parsers import ToolCallParser

# Import professional testing tools
from tests.fixtures.testing_tools import (
    create_flaky_tools, create_boundary_test_tools, create_performance_test_tools, create_load_testing_tools, create_stress_testing_tools,
    UnreliableNetworkTool, AuthenticationTool, DataCorruptionTool, 
    CircuitBreakerTool, BoundaryTestTool, SlowTool, MemoryIntensiveTool, ReliabilityTestTool,
    ThreadSafetyTestTool, VariableDelayTestTool, ParserStressTool
)
from tests.fixtures.stress_testing_tools import (
    create_concurrency_test_tools, create_parser_stress_tools, 
    create_stateful_corruption_tools, create_comprehensive_stress_tools,
    RacyTool, VariableDelayTool, RandomResponseTool, MemoryGrowthTool, StatefulCorruptionTool
)
from tests.fixtures.mock_tools import (
    create_basic_mock_tools, create_react_demo_tools, create_mixed_reliability_tools,
    MockTool, MockCalculatorTool, MockSearchTool, ConfigurableMockTool
)
from tests.fixtures.concurrent_testing_tools import (
    create_semaphore_testing_tools, create_resource_contention_tools, 
    create_timing_test_tools, create_comprehensive_concurrent_tools,
    SemaphoreTestTool, ResourceContentionTool, TimingTestTool,
    SharedCounter, SharedFileResource, ConcurrencyTracker
)


# =============================================================================
# PROFESSIONAL TESTING TOOL FIXTURES
# =============================================================================

@pytest.fixture
def advanced_testing_tools():
    """Professional testing tools for advanced failure scenarios."""
    return create_flaky_tools()

@pytest.fixture
def boundary_testing_tools():
    """Professional testing tools for boundary condition testing."""
    return create_boundary_test_tools()


@pytest.fixture
def reliability_testing_tools():
    """Create tools for reliability and failure rate testing."""
    return [
        ReliabilityTestTool("network_tool", failure_rate=0.7, delay=0.05),
        ReliabilityTestTool("api_tool", failure_rate=0.6, delay=0.1),
        ReliabilityTestTool("memory_tool", failure_rate=0.2, delay=0.02),
        ReliabilityTestTool("state_tool", failure_rate=0.3, delay=0.05)
    ]

@pytest.fixture
def performance_testing_tools():
    """Professional testing tools for performance and load testing."""
    return create_performance_test_tools()

@pytest.fixture
def load_testing_tools():
    """Reliable tools for load testing with high success rates and predictable performance."""
    return create_load_testing_tools()

@pytest.fixture
def stress_testing_tools():
    """Professional tools for extreme stress testing scenarios."""
    return create_stress_testing_tools()

@pytest.fixture
def reliable_network_tool():
    """Network tool in reliable state for baseline testing."""
    return UnreliableNetworkTool("reliable_network", "connected")

@pytest.fixture
def unreliable_network_tool():
    """Network tool in unreliable state for failure testing."""
    return UnreliableNetworkTool("unreliable_network", "slow")

@pytest.fixture
def strict_auth_tool():
    """Authentication tool with strict permissions for security testing."""
    return AuthenticationTool("strict_auth", True, {"read": True, "write": False, "admin": False})

@pytest.fixture
def permissive_auth_tool():
    """Authentication tool with permissive settings for functionality testing."""
    return AuthenticationTool("permissive_auth", True, {"read": True, "write": True, "admin": True})

# =============================================================================
# STRESS TESTING TOOL FIXTURES
# =============================================================================

@pytest.fixture
def concurrency_testing_tools():
    """Tools for concurrency and race condition testing."""
    return create_concurrency_test_tools()

@pytest.fixture
def parser_stress_testing_tools():
    """Tools for parser stress testing with chaotic inputs."""
    return create_parser_stress_tools()

@pytest.fixture
def stateful_corruption_testing_tools():
    """Tools for stateful corruption and recovery testing."""
    return create_stateful_corruption_tools()

@pytest.fixture
def comprehensive_stress_tools():
    """Complete toolkit for comprehensive stress testing."""
    return create_comprehensive_stress_tools()

# =============================================================================
# MOCK TESTING TOOL FIXTURES
# =============================================================================

@pytest.fixture
def basic_mock_tools():
    """Simple, reliable mock tools for basic testing."""
    return create_basic_mock_tools()

@pytest.fixture
def react_demo_tools():
    """Tools commonly used in ReAct demonstrations."""
    return create_react_demo_tools()

@pytest.fixture
def mixed_reliability_tools():
    """Tools with mixed reliability for error handling testing."""
    return create_mixed_reliability_tools()

@pytest.fixture
def calculator_tool():
    """Individual calculator tool for specific testing."""
    return MockCalculatorTool()

@pytest.fixture
def search_tool():
    """Individual search tool for specific testing."""
    return MockSearchTool()


# =============================================================================
# AGENT SYSTEM FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm_chat():
    """Mock LLM chat function for agent system testing."""
    def _mock_chat(messages: List[ChatMessage], tools: List[BaseTool]) -> ChatMessage:
        # Default response with tool call
        return ChatMessage(
            role=Role.ASSISTANT,
            content="I'll search for information.",
            tool_calls=[
                ToolCall(
                    name="test_tool",
                    args={"query": "test"},
                    tool_call_id="test-call-123"
                )
            ]
        )
    return _mock_chat


@pytest.fixture
def sample_chat_messages():
    """Sample chat messages for agent testing."""
    return [
        ChatMessage(role=Role.SYSTEM, content="You are a helpful assistant."),
        ChatMessage(role=Role.USER, content="What is the weather today?")
    ]


@pytest.fixture
def sample_agent_actions():
    """Sample agent actions for testing."""
    return [
        AgentAction(
            id="action-123",
            tool="test_tool",
            tool_input={"query": "test"},
            reasoning="Need to search for information"
        ),
        AgentAction(
            id="action-456", 
            tool="calculator",
            tool_input={"expression": "2 + 2"},
            reasoning="Need to calculate result"
        )
    ]


@pytest.fixture
def sample_agent_observations():
    """Sample agent observations for testing."""
    return [
        AgentObservation(
            action_id="action-123",
            tool="test_tool",
            output="Tool executed successfully",
            success=True,
            error=None,
            execution_time=0.5
        ),
        AgentObservation(
            action_id="action-456",
            tool="calculator", 
            output="4",
            success=True,
            error=None,
            execution_time=0.1
        )
    ]


@pytest.fixture
def tool_call_parser():
    """Tool call parser instance for testing."""
    return ToolCallParser()


@pytest.fixture
def mock_agent_action_executor():
    """Mock agent action executor for testing."""
    executor = Mock()
    executor.execute.return_value = AgentObservation(
        action_id="action-123",
        tool="test_tool",
        output="Mock tool result",
        success=True,
        error=None,
        execution_time=0.1
    )
    executor.execute_batch.return_value = [
        AgentObservation(
            action_id="action-123",
            tool="test_tool",
            output="Mock tool result",
            success=True,
            error=None,
            execution_time=0.1
        )
    ]
    return executor


# =============================================================================
# TOOL EXECUTION FIXTURES  
# =============================================================================

@pytest.fixture
def mock_tools():
    """Mock tools for testing."""
    tool1 = Mock(spec=BaseTool)
    tool1.name = "test_tool"
    tool1.description = "A test tool"
    
    tool2 = Mock(spec=BaseTool)
    tool2.name = "search_tool"
    tool2.description = "A search tool"
    
    tool3 = Mock(spec=BaseTool)
    tool3.name = "calculator"
    tool3.description = "A calculator tool"
    
    return [tool1, tool2, tool3]


@pytest.fixture
def mock_tool_executor_manager():
    """Mock ToolExecutorManager for testing."""
    manager = Mock()
    manager.has_tool.return_value = True
    manager.execute_requests_async.return_value = Mock()
    manager.get_health.return_value = {"status": "healthy"}
    manager.metrics = {"total_executions": 0, "success_rate": 1.0}
    return manager


# =============================================================================
# LLM INTEGRATION FIXTURES
# =============================================================================

@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    provider = Mock()
    provider.chat.return_value = ChatMessage(
        role=Role.ASSISTANT,
        content="Mock LLM response"
    )
    provider.stream.return_value = iter(["Mock", " streaming", " response"])
    provider.bind_tools.return_value = provider
    return provider


@pytest.fixture
def sample_tool_calls():
    """Sample tool calls for LLM testing."""
    return [
        ToolCall(
            name="search_tool",
            args={"query": "test query", "limit": 5},
            tool_call_id="call-123"
        ),
        ToolCall(
            name="calculator",
            args={"expression": "2 + 2"},
            tool_call_id="call-456"
        )
    ]


# =============================================================================
# STREAMING AND EVENTS FIXTURES
# =============================================================================

@pytest.fixture
def mock_stream_function():
    """Mock streaming function for testing."""
    return Mock()


@pytest.fixture
def captured_stream_events():
    """Capture streaming events for testing."""
    events = []
    
    def capture_event(event):
        events.append(event)
    
    capture_event.events = events
    return capture_event


# =============================================================================
# GRAPH ENGINE FIXTURES (Ready for future implementation)
# =============================================================================

@pytest.fixture
def mock_graph_builder():
    """Mock graph builder for future testing."""
    builder = Mock()
    builder.build.return_value = Mock()
    return builder


@pytest.fixture
def mock_graph_executor():
    """Mock graph executor for future testing."""
    executor = Mock()
    executor.execute.return_value = {"status": "completed"}
    return executor


# =============================================================================
# SESSION MANAGEMENT FIXTURES (Ready for future implementation)
# =============================================================================

@pytest.fixture
def mock_session_manager():
    """Mock session manager for future testing."""
    manager = Mock()
    manager.create_session.return_value = {"session_id": "test-session-123"}
    manager.get_session.return_value = {"session_id": "test-session-123", "state": {}}
    return manager


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def temp_directory(tmp_path):
    """Temporary directory for file-based tests."""
    return tmp_path


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "max_steps": 10,
        "timeout": 30,
        "retry_attempts": 3,
        "debug": True
    }


# =============================================================================
# CONCURRENT EXECUTION TESTING FIXTURES  
# =============================================================================

@pytest.fixture
def semaphore_testing_tools():
    """Create tools for testing semaphore/concurrency limits."""
    tools, tracker = create_semaphore_testing_tools(count=10)  # Create 10 tools for test
    return {'tools': tools, 'tracker': tracker}


@pytest.fixture
def resource_contention_tools():
    """Create tools for testing shared resource access."""
    tools, counter, file_resource = create_resource_contention_tools(count=3)
    
    # Ensure cleanup after test
    yield {'tools': tools, 'counter': counter, 'file_resource': file_resource}
    
    # Cleanup shared resources
    file_resource.cleanup()


@pytest.fixture
def timing_test_tools():
    """Create tools for performance/timing testing."""
    return create_timing_test_tools(['cpu', 'io', 'mixed'])


@pytest.fixture
def comprehensive_concurrent_tools():
    """Create comprehensive set of concurrent testing tools."""
    tools_dict = create_comprehensive_concurrent_tools()
    
    # Ensure cleanup after test
    yield tools_dict
    
    # Cleanup shared resources
    tools_dict['file_resource'].cleanup()


@pytest.fixture
def concurrency_tracker():
    """Shared concurrency tracking instance."""
    tracker = ConcurrencyTracker()
    yield tracker
    tracker.reset()


@pytest.fixture
def shared_counter():
    """Shared counter for concurrent access testing."""
    counter = SharedCounter()
    yield counter
    counter.reset()


@pytest.fixture
def shared_file_resource():
    """Shared file resource for contention testing."""
    resource = SharedFileResource()
    yield resource
    resource.cleanup()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
# Use test_helpers module for standalone helper functions

def create_step_context(uid: str, adjacent_nodes: list = None):
    """
    Factory function to create StepContext instances for testing.
    
    Args:
        uid: The unique identifier for the step
        adjacent_nodes: List of adjacent node UIDs
        
    Returns:
        StepContext instance properly configured for testing
    """
    from tests.base.test_helpers import create_test_step_context
    return create_test_step_context(uid, adjacent_nodes or [])


@pytest.fixture
def element_card():
    """Create a basic ElementCard for testing."""
    from core.models import ElementCard
    from core.enums import ResourceCategory
    
    return ElementCard(
        uid="test_element",
        category=ResourceCategory.NODE,
        type_key="test_type",
        name="Test Element",
        description="A test element for testing",
        capabilities=set(),
        reads=set(),
        writes=set(),
        instance=None,
        config={},
        skills={}
    )


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_addoption(parser):
    """Add custom command line options."""
    # E2E Stress Test Options
    parser.addoption(
        "--stress-sessions",
        action="store",
        type=int,
        default=20,
        help="Number of sessions to create in stress test (default: 20)"
    )
    parser.addoption(
        "--stress-concurrent",
        action="store",
        type=int,
        default=10,
        help="Number of concurrent executions in stress test (default: 10)"
    )
    parser.addoption(
        "--stress-base-url",
        action="store",
        default="http://localhost:8002",
        help="Base URL for API server in stress tests (default: http://localhost:8002)"
    )
    parser.addoption(
        "--blueprint-path",
        action="store",
        default=None,
        help="Path to YAML blueprint file for stress testing (e.g., run/blueprint_mcp_agent.yml)"
    )
    parser.addoption(
        "--input-text",
        action="store",
        default="What is 2+2?",
        help="Input text for stress test execution (default: 'What is 2+2?')"
    )
    parser.addoption(
        "--use-streaming",
        action="store_true",
        default=False,
        help="Use streaming execution mode (prevents gateway timeouts for high-load tests)"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests") 
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "agent_system: Agent system tests")
    config.addinivalue_line("markers", "llm_integration: LLM integration tests")
    config.addinivalue_line("markers", "tool_execution: Tool execution tests")
    config.addinivalue_line("markers", "graph_engine: Graph engine tests")
    config.addinivalue_line("markers", "session_management: Session management tests")
    config.addinivalue_line("markers", "iem_system: IEM system tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "fast: Fast running tests")
    config.addinivalue_line("markers", "stable: Stable tests")
    config.addinivalue_line("markers", "flaky: Potentially flaky tests")
    # E2E Stress Test markers
    config.addinivalue_line("markers", "stress: Stress and load tests")
    config.addinivalue_line("markers", "custom_blueprint: Tests using custom blueprints")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers."""
    for item in items:
        # Add markers based on test path
        test_path = str(item.fspath)
        
        if "/unit/" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in test_path:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in test_path:
            item.add_marker(pytest.mark.e2e)
            
        if "/agent_system/" in test_path:
            item.add_marker(pytest.mark.agent_system)
        elif "/llm_integration/" in test_path:
            item.add_marker(pytest.mark.llm_integration)
        elif "/tool_execution/" in test_path:
            item.add_marker(pytest.mark.tool_execution)
        elif "/graph_engine/" in test_path:
            item.add_marker(pytest.mark.graph_engine)
        elif "/session_management/" in test_path:
            item.add_marker(pytest.mark.session_management)


# =============================================================================
# ORCHESTRATOR INTEGRATION FIXTURES
# =============================================================================

@pytest.fixture
def predictable_llm():
    """Provide a deterministic LLM controller for testing."""
    from tests.fixtures.orchestrator_integration import PredictableLLM
    return PredictableLLM()


@pytest.fixture
def execution_tracker():
    """Provide an execution tracker for monitoring orchestrator behavior."""
    from tests.fixtures.orchestrator_integration import ExecutionTracker
    return ExecutionTracker()


@pytest.fixture
def orchestrator_integration_state(state_view):
    """Provide a state configured for orchestrator integration testing."""
    return state_view


@pytest.fixture
def orchestrator_workspace_service(orchestrator_integration_state):
    """Provide a workspace service bound to the integration state."""
    from elements.nodes.common.workload.state_bound_service import StateBoundWorkloadService
    return StateBoundWorkloadService(orchestrator_integration_state)


@pytest.fixture
def integration_orchestrator(predictable_llm, orchestrator_integration_state):
    """Provide a fully configured orchestrator for integration testing."""
    from elements.nodes.orchestrator.orchestrator_node import OrchestratorNode
    
    orchestrator = OrchestratorNode(llm=predictable_llm)
    
    # Set up context and state
    step_context = create_step_context(
        uid="test_orchestrator", 
        adjacent_nodes=["worker_1", "worker_2"]
    )
    orchestrator.set_context(step_context)
    orchestrator._state = orchestrator_integration_state
    
    return orchestrator


@pytest.fixture
def integration_task_factory():
    """Provide a factory for creating tasks for integration testing."""
    import uuid
    from elements.nodes.common.workload import Task
    
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
    from tests.fixtures.orchestrator_integration import create_planning_scenario
    return create_planning_scenario


@pytest.fixture
def synthesis_scenario_helper():
    """Provide helper for setting up synthesis scenarios."""
    from tests.fixtures.orchestrator_integration import create_synthesis_scenario
    return create_synthesis_scenario


@pytest.fixture
def task_packet_helper():
    """Provide helper for creating task packets."""
    from tests.fixtures.orchestrator_integration import create_task_packet
    return create_task_packet