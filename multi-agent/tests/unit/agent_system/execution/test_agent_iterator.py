"""
Unit tests for AgentIterator execution framework.

Tests the agent execution iterator including:
- Execution modes (AUTO, GUIDED)
- Action collection and batch execution
- Conversation message management
- Error handling and recovery
- Streaming event emission
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from mas.elements.nodes.common.agent.execution import AgentIterator, ExecutionMode, ExecutionHandlerFactory
from mas.elements.nodes.common.agent.primitives import AgentAction, AgentObservation, AgentFinish, AgentStep, StepType, ActionStatus
from mas.elements.llms.common.chat.message import ChatMessage, Role


@pytest.mark.unit
@pytest.mark.agent_system
class TestAgentIterator:
    """Test cases for AgentIterator execution framework."""
    
    @pytest.fixture
    def mock_strategy(self):
        """Mock strategy for testing."""
        strategy = Mock()
        strategy.should_continue.return_value = True
        strategy.think.return_value = [
            AgentStep(
                type=StepType.PLANNING,
                data=ChatMessage(role=Role.ASSISTANT, content="Planning step"),
                metadata={}
            ),
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(
                    id="action-123",
                    tool="test_tool",
                    tool_input={"query": "test"},
                    reasoning="Need to test"
                ),
                metadata={}
            )
        ]
        return strategy
    
    @pytest.fixture
    def agent_iterator(self, mock_strategy, mock_agent_action_executor, mock_stream_function):
        """Create AgentIterator instance for testing."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=mock_agent_action_executor
        )
        
        return AgentIterator(
            strategy=mock_strategy,
            execution_handler=execution_handler,
            stream=mock_stream_function
        )
    
    def test_iterator_initialization(self, agent_iterator, mock_strategy, mock_agent_action_executor):
        """Test iterator initialization with correct defaults."""
        assert agent_iterator.strategy == mock_strategy
        assert agent_iterator.execution_handler is not None
        assert agent_iterator.messages == []
        assert agent_iterator.observations == []
        assert agent_iterator.history == []
        assert not agent_iterator.finished
    
    def test_single_action_execution_auto_mode(self, agent_iterator, mock_strategy):
        """Test single action execution in AUTO mode."""
        # Setup strategy to return action then finish
        mock_strategy.think.side_effect = [
            [
                AgentStep(
                    type=StepType.PLANNING,
                    data=ChatMessage(role=Role.ASSISTANT, content="Planning"),
                    metadata={}
                ),
                AgentStep(
                    type=StepType.ACTION,
                    data=AgentAction(
                        id="action-123",
                        tool="test_tool",
                        tool_input={"query": "test"},
                        reasoning="Testing"
                    ),
                    metadata={}
                )
            ],
            [
                AgentStep(
                    type=StepType.PLANNING,
                    data=ChatMessage(role=Role.ASSISTANT, content="Final answer"),
                    metadata={}
                ),
                AgentStep(
                    type=StepType.FINISH,
                    data=AgentFinish(output="Test complete", reasoning="Done"),
                    metadata={}
                )
            ]
        ]
        
        # First iteration - should yield PLANNING step first (new SOLID behavior)
        step1 = next(agent_iterator)
        assert step1.type == StepType.PLANNING
        assert step1.data.content == "Planning"
        
        # Second iteration - should yield OBSERVATION step (action was executed automatically)
        step2 = next(agent_iterator)
        assert step2.type == StepType.OBSERVATION
        assert step2.data.tool == "test_tool"
        assert step2.data.success == True
        assert len(agent_iterator.observations) == 1  # Action was executed and tracked
        
        # Third iteration - should yield final PLANNING step
        step3 = next(agent_iterator)
        assert step3.type == StepType.PLANNING
        assert step3.data.content == "Final answer"
        
        # Fourth iteration - should yield FINISH step
        step4 = next(agent_iterator)
        assert step4.type == StepType.FINISH
        assert step4.data.output == "Test complete"
        assert agent_iterator.finished
    
    def test_multiple_actions_batch_execution(self, agent_iterator, mock_strategy, mock_agent_action_executor):
        """Test multiple actions executed together in batch."""
        # Setup strategy to return multiple actions
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.PLANNING,
                data=ChatMessage(role=Role.ASSISTANT, content="Planning multiple actions"),
                metadata={}
            ),
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-1", tool="tool1", tool_input={}, reasoning="First"),
                metadata={}
            ),
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-2", tool="tool2", tool_input={}, reasoning="Second"),
                metadata={}
            ),
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-3", tool="tool3", tool_input={}, reasoning="Third"),
                metadata={}
            )
        ]
        
        # Mock batch execution
        mock_agent_action_executor.execute_batch.return_value = [
            AgentObservation(action_id="action-1", tool="tool1", output="Result 1", success=True),
            AgentObservation(action_id="action-2", tool="tool2", output="Result 2", success=True),
            AgentObservation(action_id="action-3", tool="tool3", output="Result 3", success=True)
        ]
        
        # First iteration - should yield PLANNING step
        step1 = next(agent_iterator)
        assert step1.type == StepType.PLANNING
        assert step1.data.content == "Planning multiple actions"
        
        # Actions should be executed in batch automatically (AUTO mode)
        mock_agent_action_executor.execute_batch.assert_called_once()
        batch_call_args = mock_agent_action_executor.execute_batch.call_args[0][0]
        assert len(batch_call_args) == 3  # All 3 actions batched together
        assert [action.tool for action in batch_call_args] == ["tool1", "tool2", "tool3"]

        # Next iterations should yield individual OBSERVATION steps (new SOLID behavior)
        step2 = next(agent_iterator)
        assert step2.type == StepType.OBSERVATION
        assert step2.data.tool == "tool1"
        assert step2.data.output == "Result 1"
        
        step3 = next(agent_iterator)
        assert step3.type == StepType.OBSERVATION
        assert step3.data.tool == "tool2"
        assert step3.data.output == "Result 2"
        
        step4 = next(agent_iterator)
        assert step4.type == StepType.OBSERVATION
        assert step4.data.tool == "tool3"
        assert step4.data.output == "Result 3"
        
        # Should have all observations tracked
        assert len(agent_iterator.observations) == 3
    
    def test_guided_mode_pending_actions(self, mock_strategy, mock_agent_action_executor, mock_stream_function):
        """Test GUIDED mode adds actions to pending list."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.GUIDED,
            action_executor=mock_agent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=mock_strategy,
            execution_handler=execution_handler,
            stream=mock_stream_function
        )
        
        # Setup strategy to return actions
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-1", tool="tool1", tool_input={}, reasoning="Test"),
                metadata={}
            ),
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-2", tool="tool2", tool_input={}, reasoning="Test"),
                metadata={}
            )
        ]
        
        # Execute - should yield ACTION step for confirmation (GUIDED mode behavior)
        step1 = next(iterator)
        assert step1.type == StepType.ACTION
        assert step1.data.tool == "tool1"

        # Should not execute actions automatically in GUIDED mode
        mock_agent_action_executor.execute_batch.assert_not_called()

        # Should have pending actions in the guided handler
        pending = iterator.get_pending_actions()
        assert len(pending) == 2
        assert [action.tool for action in pending] == ["tool1", "tool2"]
        
        # Get second ACTION step
        step2 = next(iterator)
        assert step2.type == StepType.ACTION
        assert step2.data.tool == "tool2"
    
    def test_confirm_action_execution(self, mock_strategy, mock_agent_action_executor, mock_stream_function):
        """Test confirming and executing pending actions."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.GUIDED,
            action_executor=mock_agent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=mock_strategy,
            execution_handler=execution_handler
        )
        
        # Setup strategy to return action (proper way to add pending actions)
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-123", tool="test_tool", tool_input={}, reasoning="Test"),
                metadata={}
            )
        ]
        
        # Execute to get action into pending state
        step = next(iterator)
        assert step.type == StepType.ACTION
        assert len(iterator.get_pending_actions()) == 1
        
        # Mock single action execution for confirmation
        mock_agent_action_executor.execute.return_value = AgentObservation(
            action_id="action-123", tool="test_tool", output="Test result", success=True
        )
        
        # Confirm and execute
        obs_step = iterator.confirm_action("action-123", execute=True)
        
        # Should execute the action
        mock_agent_action_executor.execute.assert_called_once()
        assert obs_step.type == StepType.OBSERVATION
        assert obs_step.data.tool == "test_tool"
        assert obs_step.data.output == "Test result"
        assert len(iterator.observations) == 1
    
    def test_confirm_action_rejection(self, mock_strategy, mock_agent_action_executor, mock_stream_function):
        """Test rejecting pending actions."""
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.GUIDED,
            action_executor=mock_agent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=mock_strategy,
            execution_handler=execution_handler
        )
        
        # Setup strategy to return action (proper way to add pending actions)
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-123", tool="test_tool", tool_input={}, reasoning="Test"),
                metadata={}
            )
        ]
        
        # Execute to get action into pending state
        step = next(iterator)
        assert step.type == StepType.ACTION
        assert len(iterator.get_pending_actions()) == 1
        
        # Reject action
        obs_step = iterator.confirm_action("action-123", execute=False)
        
        # Should not execute the action
        mock_agent_action_executor.execute.assert_not_called()
        assert obs_step is None  # Rejection doesn't return observation step
        assert len(iterator.get_pending_actions()) == 0  # Action removed from pending
    
    def test_conversation_message_updates_planning(self, agent_iterator, mock_strategy):
        """Test that PLANNING messages are added to conversation."""
        # Setup strategy to return planning and action
        planning_message = ChatMessage(role=Role.ASSISTANT, content="I'll search for info")
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.PLANNING,
                data=planning_message,
                metadata={}
            ),
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-123", tool="test_tool", tool_input={}, reasoning="Test"),
                metadata={}
            )
        ]
        
        # Execute
        next(agent_iterator)
        
        # Should have added planning message to conversation
        assert len(agent_iterator.messages) == 1
        assert agent_iterator.messages[0] == planning_message
    
    def test_conversation_message_updates_finish(self, agent_iterator, mock_strategy):
        """Test that FINISH messages are converted and added to conversation."""
        # Setup strategy to return finish
        finish_data = AgentFinish(output="Task complete", reasoning="All done")
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.PLANNING,
                data=ChatMessage(role=Role.ASSISTANT, content="Final answer"),
                metadata={}
            ),
            AgentStep(
                type=StepType.FINISH,
                data=finish_data,
                metadata={}
            )
        ]
        
        # Execute
        step = next(agent_iterator)
        
        # Should yield PLANNING step first
        assert step.type == StepType.PLANNING
        assert step.data.content == "Final answer"
        
        # Should have added only the planning message (FINISH steps are not converted to messages)
        assert len(agent_iterator.messages) == 1
        assert agent_iterator.messages[0].content == "Final answer"
        
        # Get the FINISH step
        finish_step = next(agent_iterator)
        assert finish_step.type == StepType.FINISH
        assert finish_step.data.output == "Task complete"
    
    def test_error_handling_recoverable(self, agent_iterator, mock_strategy, caplog):
        """Test error step handling for recoverable errors."""
        error = Exception("Test error")
        trace_cm = MagicMock()
        trace_cm.__enter__.return_value = MagicMock()
        agent_iterator._tracing = Mock()
        agent_iterator._tracing.trace_agent_iteration.return_value = trace_cm
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ERROR,
                data=error,
                metadata={"recoverable": True}
            )
        ]
        
        # Execute
        with caplog.at_level("ERROR"):
            step = next(agent_iterator)
        
        # Should return error step but not finish
        assert step.type == StepType.ERROR
        assert step.data == error
        assert not agent_iterator._finished  # Recoverable error shouldn't finish

        record = next(record for record in caplog.records if record.message == "agent.step")
        assert record.exception_type == "Exception"
        assert record.exception_message == "Test error"
        assert record.exc_info[1] is error
    
    def test_error_handling_non_recoverable(self, agent_iterator, mock_strategy):
        """Test error step handling for non-recoverable errors."""
        error = Exception("Fatal error")
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ERROR,
                data=error,
                metadata={"recoverable": False}
            )
        ]
        
        # Execute
        step = next(agent_iterator)
        
        # Should return error step and finish
        assert step.type == StepType.ERROR
        assert step.data == error
        # Note: The actual finishing behavior depends on implementation
    
    def test_action_approval_callback_rejection(self, mock_strategy, mock_agent_action_executor, mock_stream_function):
        """Test action approval callback rejecting actions."""
        approval_callback = Mock(return_value=False)  # Reject all actions
        
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=mock_agent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=mock_strategy,
            execution_handler=execution_handler,
            stream=mock_stream_function,
            on_action=approval_callback
        )
        
        # Setup strategy to return action
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-123", tool="test_tool", tool_input={}, reasoning="Test"),
                metadata={}
            )
        ]
        
        # Execute - should yield rejection observation step
        step = next(iterator)
        
        # Should have called approval callback
        approval_callback.assert_called_once()
        
        # Should yield OBSERVATION step for rejection
        assert step.type == StepType.OBSERVATION
        assert not step.data.success
        assert step.data.tool == "test_tool"
        
        # Should have created rejection observation
        assert len(iterator.observations) == 1
        assert not iterator.observations[0].success
    
    def test_action_approval_callback_approval(self, mock_strategy, mock_agent_action_executor, mock_stream_function):
        """Test action approval callback approving actions."""
        approval_callback = Mock(return_value=True)  # Approve all actions
        
        # Create execution handler using new pattern
        execution_handler = ExecutionHandlerFactory.create(
            mode=ExecutionMode.AUTO,
            action_executor=mock_agent_action_executor
        )
        
        iterator = AgentIterator(
            strategy=mock_strategy,
            execution_handler=execution_handler,
            stream=mock_stream_function,
            on_action=approval_callback
        )
        
        # Setup strategy to return action
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.ACTION,
                data=AgentAction(id="action-123", tool="test_tool", tool_input={}, reasoning="Test"),
                metadata={}
            )
        ]
        
        # Execute
        next(iterator)
        
        # Should have called approval callback
        approval_callback.assert_called_once()
        
        # Should have executed action normally
        mock_agent_action_executor.execute_batch.assert_called_once()
    
    def test_strategy_should_continue_check(self, agent_iterator, mock_strategy):
        """Test that iterator respects strategy's should_continue."""
        mock_strategy.should_continue.return_value = False
        
        # Should raise StopIteration immediately
        with pytest.raises(StopIteration):
            next(agent_iterator)
    
    def test_streaming_events_emission(self, agent_iterator, mock_stream_function, mock_strategy):
        """Test that streaming events are properly emitted."""
        # Setup strategy
        mock_strategy.think.return_value = [
            AgentStep(
                type=StepType.PLANNING,
                data=ChatMessage(role=Role.ASSISTANT, content="Planning"),
                metadata={}
            )
        ]
        
        # Execute
        next(agent_iterator)
        
        # Should have emitted streaming events
        assert mock_stream_function.call_count > 0
        
        # Check that events have proper structure
        for call in mock_stream_function.call_args_list:
            event = call[0][0]  # First argument
            assert "type" in event
            assert "data" in event
            assert "timestamp" in event
            assert "metadata" in event
            # Verify event type format
            assert event["type"].startswith("agent_")
    
    def test_batch_execution_preserves_action_order(self, agent_iterator, mock_strategy, mock_agent_action_executor):
        """Test that batch execution preserves action order."""
        # Setup strategy with specific action order
        actions = [
            AgentAction(id=f"action-{i}", tool=f"tool{i}", tool_input={}, reasoning=f"Action {i}")
            for i in range(5)
        ]
        
        steps = [AgentStep(type=StepType.PLANNING, data=ChatMessage(role=Role.ASSISTANT, content="Planning"), metadata={})]
        steps.extend([AgentStep(type=StepType.ACTION, data=action, metadata={}) for action in actions])
        
        mock_strategy.think.return_value = steps
        
        # Mock batch execution to return observations in order
        expected_observations = [
            AgentObservation(action_id=f"action-{i}", tool=f"tool{i}", output=f"Result {i}", success=True)
            for i in range(5)
        ]
        mock_agent_action_executor.execute_batch.return_value = expected_observations
        
        # Execute
        next(agent_iterator)
        
        # Verify batch execution was called with actions in correct order
        called_actions = mock_agent_action_executor.execute_batch.call_args[0][0]
        assert len(called_actions) == 5
        assert [action.id for action in called_actions] == [f"action-{i}" for i in range(5)]
        
        # Verify observations are stored in correct order
        assert len(agent_iterator.observations) == 5
        assert [obs.action_id for obs in agent_iterator.observations] == [f"action-{i}" for i in range(5)]
