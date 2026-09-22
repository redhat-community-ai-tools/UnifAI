"""
Unit tests for ReAct (Reasoning + Acting) strategy.

Tests the core ReAct strategy logic including:
- Strategy initialization and configuration
- Tool call generation and parsing
- Final answer generation
- Error handling and recovery
- Context building and conversation flow
"""

import pytest
from unittest.mock import Mock, patch
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from mas.elements.nodes.common.agent.strategies.react import ReActStrategy
from mas.elements.nodes.common.agent.primitives import AgentAction, AgentObservation, AgentFinish, StepType
from mas.elements.nodes.common.agent.parsers import ParseError, ParseErrorType
from mas.elements.nodes.common.agent.constants import StrategyType


@pytest.mark.unit
@pytest.mark.agent_system
class TestReActStrategy:
    """Test cases for ReAct strategy implementation."""
    
    @pytest.fixture
    def react_strategy(self, mock_llm_chat, mock_tools, tool_call_parser):
        """Create ReActStrategy instance for testing."""
        return ReActStrategy(
            llm_chat=mock_llm_chat,
            tools=mock_tools,
            parser=tool_call_parser,
            max_steps=5,
            min_reasoning_length=10
        )
    
    def test_strategy_initialization(self, react_strategy, mock_tools):
        """Test strategy initialization and basic properties."""
        assert react_strategy.strategy_name == StrategyType.REACT.value
        assert react_strategy.max_steps == 5
        assert react_strategy.min_reasoning_length == 10
        assert len(react_strategy.all_tools) == len(mock_tools)
        assert react_strategy._step_count == 0
    
    def test_get_tools_for_phase_returns_all_tools(self, react_strategy, mock_tools):
        """Test that ReAct returns all tools for any phase."""
        tools = react_strategy.get_tools_for_phase("any_phase")
        assert len(tools) == len(mock_tools)
        assert all(tool in mock_tools for tool in tools)
    
    def test_think_with_single_tool_call(self, react_strategy, sample_chat_messages):
        """Test think method when LLM returns single tool call."""
        mock_response = ChatMessage(
            role=Role.ASSISTANT,
            content="I need to search for information.",
            tool_calls=[
                ToolCall(name="test_tool", args={"query": "test"}, tool_call_id="call-123")
            ]
        )
        
        with patch.object(react_strategy, 'llm_chat', return_value=mock_response):
            steps = react_strategy.think(sample_chat_messages, [])
        
        assert len(steps) == 2  # PLANNING + ACTION
        assert steps[0].type == StepType.PLANNING
        assert steps[1].type == StepType.ACTION
        assert isinstance(steps[1].data, AgentAction)
        assert steps[1].data.tool == "test_tool"
        assert steps[1].data.id == "call-123"

    def test_logs_interaction_start_before_calling_llm(
        self, react_strategy, sample_chat_messages, caplog
    ):
        """The start event distinguishes pre-LLM failures from LLM failures."""
        with patch.object(react_strategy, "llm_chat", side_effect=RuntimeError("unavailable")) as llm_chat:
            with caplog.at_level("INFO"):
                react_strategy.think(sample_chat_messages)

        record = next(
            record for record in caplog.records if record.message == "llm.interaction_start"
        )
        assert record.strategy == "react"
        assert record.interaction_number == 1
        assert llm_chat.called
    
    def test_think_with_multiple_tool_calls(self, react_strategy, sample_chat_messages):
        """Test think method when LLM returns multiple tool calls."""
        mock_response = ChatMessage(
            role=Role.ASSISTANT,
            content="I need to use multiple tools.",
            tool_calls=[
                ToolCall(name="tool1", args={"query": "test1"}, tool_call_id="call-1"),
                ToolCall(name="tool2", args={"query": "test2"}, tool_call_id="call-2"),
                ToolCall(name="tool1", args={"query": "test3"}, tool_call_id="call-3")
            ]
        )
        
        with patch.object(react_strategy, 'llm_chat', return_value=mock_response):
            steps = react_strategy.think(sample_chat_messages, [])
        
        # Should have 1 PLANNING + 3 ACTION steps
        assert len(steps) == 4
        assert steps[0].type == StepType.PLANNING
        
        action_steps = [step for step in steps if step.type == StepType.ACTION]
        assert len(action_steps) == 3
        
        # Check tool names and IDs
        tool_names = [step.data.tool for step in action_steps]
        tool_ids = [step.data.id for step in action_steps]
        assert tool_names == ["tool1", "tool2", "tool1"]
        assert tool_ids == ["call-1", "call-2", "call-3"]
    
    def test_think_with_final_answer(self, react_strategy, sample_chat_messages):
        """Test think method when LLM returns final answer."""
        mock_response = ChatMessage(
            role=Role.ASSISTANT,
            content="The weather is sunny today. This is a complete answer with sufficient reasoning."
        )
        
        # Mock parser to return AgentFinish
        with patch.object(react_strategy, 'llm_chat', return_value=mock_response), \
             patch.object(react_strategy.parser, 'parse') as mock_parse:
            
            mock_parse.return_value = AgentFinish(
                output="The weather is sunny today.",
                reasoning="Complete answer"
            )
            
            steps = react_strategy.think(sample_chat_messages, [])
        
        assert len(steps) == 2  # PLANNING + FINISH
        assert steps[0].type == StepType.PLANNING
        assert steps[1].type == StepType.FINISH
        assert isinstance(steps[1].data, AgentFinish)
    
    def test_think_with_parse_error(self, react_strategy, sample_chat_messages):
        """Test think method when parsing fails."""
        mock_response = ChatMessage(
            role=Role.ASSISTANT,
            content="Invalid response"
        )
        
        parse_error = ParseError(
            "Invalid format",
            ParseErrorType.INVALID_FORMAT,
            "Invalid response",
            recoverable=True
        )
        
        # Mock the SystemError.from_parse_error to avoid constants import issue
        with patch.object(react_strategy, 'llm_chat', return_value=mock_response), \
             patch.object(react_strategy.parser, 'parse', side_effect=parse_error), \
             patch('elements.nodes.common.agent.primitives.SystemError.from_parse_error') as mock_system_error:
            
            from mas.elements.nodes.common.agent.primitives import SystemError
            mock_system_error.return_value = SystemError(
                message="Parse error occurred",
                error_type="parse_error",
                raw_output="Invalid response",
                guidance="Please provide valid format",
                recoverable=True
            )
            
            steps = react_strategy.think(sample_chat_messages, [])
        
        assert len(steps) == 1
        assert steps[0].type == StepType.ERROR
        assert steps[0].data == parse_error
        assert react_strategy._pending_system_error is not None
    
    def test_reasoning_validation_too_short(self, react_strategy, sample_chat_messages):
        """Test reasoning validation fails for short responses."""
        mock_response = ChatMessage(
            role=Role.ASSISTANT,
            content="Short"  # Less than min_reasoning_length (10)
        )
        
        # Mock parser to return AgentFinish (which triggers validation)
        with patch.object(react_strategy, 'llm_chat', return_value=mock_response), \
             patch.object(react_strategy.parser, 'parse') as mock_parse, \
             patch('elements.nodes.common.agent.primitives.SystemError.from_parse_error') as mock_system_error:
            
            from mas.elements.nodes.common.agent.primitives import SystemError
            mock_system_error.return_value = SystemError(
                message="Reasoning too short",
                error_type="validation_error",
                raw_output="Short",
                guidance="Please provide more detailed reasoning",
                recoverable=True
            )
            
            mock_parse.return_value = AgentFinish(
                output="Short answer",
                reasoning="Short"
            )
            
            steps = react_strategy.think(sample_chat_messages, [])
        
        assert len(steps) == 1
        assert steps[0].type == StepType.ERROR
        assert isinstance(steps[0].data, ParseError)
        assert "Reasoning too short" in str(steps[0].data)
    
    def test_build_context_with_observations(self, react_strategy, sample_chat_messages, sample_agent_observations):
        """Test context building with tool observations."""
        context = react_strategy.build_context(sample_chat_messages, sample_agent_observations)
        
        # Should have: system + user + tool messages
        assert len(context) >= 3
        
        # Check that tool messages are properly formatted
        tool_messages = [msg for msg in context if msg.role == Role.TOOL]
        assert len(tool_messages) == len(sample_agent_observations)
        
        for tool_msg, obs in zip(tool_messages, sample_agent_observations):
            assert tool_msg.tool_call_id == obs.action_id
            assert obs.output in tool_msg.content
    
    def test_should_continue_max_steps_reached(self, react_strategy):
        """Test should_continue returns False when max steps reached."""
        react_strategy._step_count = react_strategy.max_steps
        assert not react_strategy.should_continue([])
    
    def test_should_continue_terminal_step(self, react_strategy):
        """Test should_continue returns False for terminal steps."""
        from mas.elements.nodes.common.agent.primitives import AgentStep
        
        # Create a FINISH step (which is inherently terminal)
        terminal_step = AgentStep(
            type=StepType.FINISH,
            data=AgentFinish(output="Done", reasoning="Complete"),
            metadata={}
        )
        
        # FINISH steps are terminal by nature
        assert not react_strategy.should_continue([terminal_step])
    
    def test_system_message_priority(self, mock_llm_chat, mock_tools, tool_call_parser):
        """Test that node system message takes priority over default."""
        custom_message = "Custom system message from node"
        
        strategy = ReActStrategy(
            llm_chat=mock_llm_chat,
            tools=mock_tools,
            parser=tool_call_parser,
            system_message=custom_message
        )
        
        assert strategy.system_message == custom_message
        
        # Test context building uses custom message
        context = strategy._build_base_context([
            ChatMessage(role=Role.USER, content="Test")
        ])
        
        assert context[0].role == Role.SYSTEM
        assert context[0].content == custom_message
    
    @pytest.mark.parametrize("consecutive_errors,should_continue", [
        (0, True),   # No errors - should continue
        (1, False),  # Any ERROR step is terminal - should stop
        (2, False),  # Any ERROR step is terminal - should stop  
        (3, False),  # Any ERROR step is terminal - should stop
        (4, False)   # Any ERROR step is terminal - should stop
    ])
    def test_consecutive_error_handling(self, react_strategy, consecutive_errors, should_continue):
        """Test that strategy stops after any error (ERROR steps are terminal)."""
        from mas.elements.nodes.common.agent.primitives import AgentStep
        
        # Create history with consecutive errors
        history = []
        for i in range(consecutive_errors):
            error_step = AgentStep(
                type=StepType.ERROR,  # ERROR steps are terminal by nature
                data=Exception(f"Error {i}"),
                metadata={}
            )
            history.append(error_step)
        
        # ERROR steps are terminal, so any ERROR in history should stop execution
        assert react_strategy.should_continue(history) == should_continue
    
    def test_error_recovery_with_system_feedback(self, react_strategy, sample_chat_messages):
        """Test that strategy provides system feedback after errors."""
        # First call - cause error
        parse_error = ParseError(
            "Invalid format",
            ParseErrorType.INVALID_FORMAT,
            "Invalid response",
            recoverable=True
        )
        
        with patch.object(react_strategy, 'llm_chat') as mock_llm, \
             patch.object(react_strategy.parser, 'parse', side_effect=parse_error), \
             patch('elements.nodes.common.agent.primitives.SystemError.from_parse_error') as mock_system_error:
            
            from mas.elements.nodes.common.agent.primitives import SystemError
            mock_system_error.return_value = SystemError(
                message="Parse error occurred",
                error_type="parse_error",
                raw_output="Invalid response",
                guidance="Please provide valid format",
                recoverable=True
            )
            
            steps = react_strategy.think(sample_chat_messages, [])
            assert steps[0].type == StepType.ERROR
        
        # Second call - should include error feedback in context
        mock_llm.return_value = ChatMessage(role=Role.ASSISTANT, content="Fixed response")
        
        with patch.object(react_strategy.parser, 'parse') as mock_parse:
            mock_parse.return_value = AgentFinish(output="Success", reasoning="Fixed")
            
            steps = react_strategy.think(sample_chat_messages, [])
            
            # Verify the strategy recovered and produced success steps
            assert len(steps) == 2  # PLANNING + FINISH
            assert steps[0].type == StepType.PLANNING
            assert steps[1].type == StepType.FINISH
            assert isinstance(steps[1].data, AgentFinish)
            
            # Verify that pending error was cleared after successful recovery
            assert react_strategy._pending_system_error is None
