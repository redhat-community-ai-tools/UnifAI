"""
Agent system constants and enums.

This module centralizes all hard-coded values, magic strings, and configuration
constants used throughout the agent system. Provides type-safe enums and
configurable constants.

Design Principles:
- Single Source of Truth: All constants in one place
- Type Safety: Use enums for fixed sets of values
- Configurability: Easy to modify behavior by changing constants
- Documentation: Clear descriptions for all values
"""

from enum import Enum
from typing import Dict, Any, List, Set
from dataclasses import dataclass


# =============================================================================
# STRATEGY RELATED CONSTANTS
# =============================================================================

class StrategyType(Enum):
    """Available agent strategy types."""
    REACT = "react"
    PLAN_AND_EXECUTE = "plan_and_execute"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    REFLEXION = "reflexion"
    CUSTOM = "custom"


class StrategyDefaults:
    """Default values for strategy configuration."""
    MAX_STEPS = 10
    MIN_REASONING_LENGTH = 10
    REFLECT_ON_ERRORS = True
    CONSECUTIVE_ERROR_LIMIT = 3


# =============================================================================
# TOOL RELATED CONSTANTS  
# =============================================================================

class SpecialToolNames(Enum):
    """Names of special built-in tools."""
    PARSE_ERROR = "_parse_error"
    INVALID_TOOL = "_invalid_tool"
    FORMAT_ERROR = "_format_error"
    TOOL_CALL_ERROR = "_tool_call_error"
    MISSING_CONTENT = "_missing_content"
    JSON_PARSE_ERROR = "_json_parse_error"
    TEXT_FORMAT_ERROR = "_text_format_error"
    GENERIC_ERROR = "_generic_error"


class ToolHandlingPolicy(Enum):
    """Policies for handling missing/invalid tools."""
    ERROR = "error"        # Raise error immediately
    IGNORE = "ignore"      # Skip the tool call
    REFLECT = "reflect"    # Create reflection action


class ToolExecutionDefaults:
    """Default values for tool execution."""
    VALIDATE_ARGS = True
    ON_MISSING_TOOL = ToolHandlingPolicy.REFLECT
    MAX_TOOL_CALLS_PER_MESSAGE = 10
    REQUIRE_TOOL_CALL_ID = True
    ALLOW_EMPTY_ARGS = True


# =============================================================================
# EXECUTION RELATED CONSTANTS
# =============================================================================

class EarlyStoppingPolicy(Enum):
    """Policies for early stopping during execution."""
    FIRST_FINISH = "first_finish"    # Stop on first finish step
    FIRST_ERROR = "first_error"      # Stop on first error
    ALL_ACTIONS = "all_actions"      # Complete all pending actions
    NEVER = "never"                  # Never stop early
    FORCE = "force"                  # Force stop immediately


class ExecutionDefaults:
    """Default values for execution configuration."""
    MAX_EXECUTION_TIME = 300.0  # 5 minutes
    MAX_ACTIONS_PER_MINUTE = 60
    TIMEOUT_MESSAGE = "Agent execution timed out"
    MAX_CONSECUTIVE_ERRORS = 3
    RETURN_INTERMEDIATE = False
    MAX_STEPS = 10  # Default maximum steps  
    REFLECT_ON_ERRORS = True  # Default error reflection


# =============================================================================
# PARSER RELATED CONSTANTS
# =============================================================================

class ParserType(Enum):
    """Available parser types."""
    TOOL_CALL = "tool_call"
    TEXT = "text" 
    JSON = "json"
    MULTI = "multi"
    CUSTOM = "custom"


class ParserDefaults:
    """Default values for parser configuration."""
    MIN_CONTENT_LENGTH = 1
    MAX_CONTENT_LENGTH = 50000
    VALIDATE_SCHEMA = True
    FALLBACK_TO_CONTENT = True
    STRICT_FORMAT = False
    CASE_SENSITIVE = False


# =============================================================================
# SYSTEM PROMPTS AND TEMPLATES
# =============================================================================

class SystemPrompts:
    """Default system prompts for different strategies."""
    
    REACT_DEFAULT = """You are a helpful assistant that uses tools to answer questions.

For each step, you should:
1. Think about the current situation and what you need to do
2. Choose an appropriate tool and provide the necessary input, OR provide a final answer
3. Wait for the observation from the tool
4. Repeat until you can provide a final answer

Guidelines:
- Always reason about your next action before taking it
- Use tools when you need additional information or to perform actions
- Provide clear, helpful final answers
- If you encounter errors, reflect on what went wrong and try a different approach

You have access to the following tools through function calls. When you want to use a tool, make a function call with the appropriate parameters.

Remember: Think step by step and be thorough in your reasoning."""

    PLAN_AND_EXECUTE = """You are an intelligent planning agent. Your task is to:

1. Analyze the given problem thoroughly
2. Create a detailed plan with specific steps
3. Execute each step systematically
4. Adjust the plan based on observations
5. Provide a comprehensive final answer

Planning Guidelines:
- Break down complex tasks into manageable steps
- Consider dependencies between steps
- Plan for potential failures and alternatives
- Use available tools effectively
- Document your reasoning at each stage"""


# =============================================================================
# ERROR MESSAGES AND GUIDANCE
# =============================================================================

class ErrorMessages:
    """Standard error messages and guidance."""
    
    TOOL_CALL_FORMAT = (
        "Tool calls must have valid names and properly formatted arguments. "
        "Ensure all required fields are present and arguments are correct types."
    )
    
    JSON_FORMAT = (
        "Ensure JSON is valid and matches the expected schema. "
        "Check for proper quotes, brackets, and comma placement."
    )
    
    TEXT_FORMAT = (
        "Follow the expected text format exactly. "
        "Use the specified patterns for actions and final answers."
    )
    
    MISSING_CONTENT = (
        "Responses should either contain tool calls for actions or "
        "text content for final answers. Empty responses are not helpful."
    )
    
    VALIDATION_FAILED = (
        "Input validation failed. Check that all required parameters "
        "are provided and have the correct types and values."
    )
    
    UNKNOWN_STRATEGY_TYPE = (
        "Unknown strategy type. Available types: {available_types}"
    )
    
    @staticmethod
    def get_parse_error_guidance(parse_error) -> str:
        """Get clean, actionable guidance for parse errors."""
        from ..parsers.base import ParseError, ParseErrorType
        
        if not isinstance(parse_error, ParseError):
            return f"Parsing failed: {parse_error}. Please check your output format."
        
        base_message = f"Your previous response had formatting issues: {parse_error}"
        
        guidance_map = {
            ParseErrorType.JSON_ERROR: f"{base_message}\n\n{ErrorMessages.JSON_FORMAT}",
            ParseErrorType.TOOL_CALL_ERROR: f"{base_message}\n\n{ErrorMessages.TOOL_CALL_FORMAT}",
            ParseErrorType.INVALID_FORMAT: f"{base_message}\n\n{ErrorMessages.TEXT_FORMAT}",
            ParseErrorType.MISSING_CONTENT: f"{base_message}\n\n{ErrorMessages.MISSING_CONTENT}",
            ParseErrorType.VALIDATION_ERROR: f"{base_message}\n\n{ErrorMessages.VALIDATION_FAILED}",
        }
        
        guidance = guidance_map.get(
            parse_error.error_type, 
            f"{base_message}\n\nPlease follow the expected format."
        )
        
        # Add raw output if available (truncated)
        if hasattr(parse_error, 'raw_output') and parse_error.raw_output:
            raw_output = parse_error.raw_output[:200]
            if len(parse_error.raw_output) > 200:
                raw_output += "..."
            guidance += f"\n\nYour output: {raw_output}"
        
        return guidance


# =============================================================================
# FIELD MAPPINGS FOR DIFFERENT FORMATS
# =============================================================================

@dataclass
class FieldMappings:
    """Field name mappings for different response formats."""
    action_field: str = "action"
    input_field: str = "input"
    type_field: str = "type"
    output_field: str = "output"
    reasoning_field: str = "reasoning"
    thought_field: str = "thought"
    observation_field: str = "observation"
    finish_field: str = "finish"


# =============================================================================
# PRIORITY AND SCORING VALUES
# =============================================================================

class ParserPriorities:
    """Priority values for parser selection."""
    TOOL_CALL = 90    # Highest priority (default)
    JSON = 80         # High priority
    TEXT = 70         # Medium priority
    CUSTOM = 50       # Default priority


class ValidationLimits:
    """Limits for validation and safety checks."""
    MAX_REASONING_LENGTH = 10000
    MIN_REASONING_LENGTH = 10
    MAX_TOOL_NAME_LENGTH = 100
    MAX_ERROR_MESSAGE_LENGTH = 1000
    MAX_RETRY_ATTEMPTS = 3
    MIN_EXECUTION_INTERVAL = 0.1  # Seconds between actions


# =============================================================================
# FORMAT EXAMPLES AND TEMPLATES
# =============================================================================

class FormatExamples:
    """Example formats for different parser types."""
    
    TOOL_CALL_ACTION = {
        "name": "calculator",
        "arguments": {"expression": "5 + 3"}
    }
    
    JSON_ACTION = {
        "type": "action",
        "action": "calculator", 
        "input": {"expression": "5 + 3"},
        "reasoning": "I need to calculate the sum"
    }
    
    JSON_FINISH = {
        "type": "finish",
        "output": "The answer is 8",
        "reasoning": "Calculation complete"
    }
    
    REACT_ACTION = """Thought: I need to calculate the result
Action: calculator
Action Input: {"expression": "5 + 3"}"""
    
    REACT_FINISH = "Final Answer: The result is 8"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_default_config(component_type: str) -> Dict[str, Any]:
    """
    Get default configuration for a component type.
    
    Args:
        component_type: Type of component (strategy, parser, executor, etc.)
        
    Returns:
        Dictionary with default configuration values
    """
    defaults = {
        "strategy": {
            "max_steps": StrategyDefaults.MAX_STEPS,
            "reflect_on_errors": StrategyDefaults.REFLECT_ON_ERRORS,
            "min_reasoning_length": StrategyDefaults.MIN_REASONING_LENGTH
        },
        "parser": {
            "min_content_length": ParserDefaults.MIN_CONTENT_LENGTH,
            "max_content_length": ParserDefaults.MAX_CONTENT_LENGTH,
            "validate_schema": ParserDefaults.VALIDATE_SCHEMA,
            "fallback_to_content": ParserDefaults.FALLBACK_TO_CONTENT
        },
        "executor": {
            "validate_args": ToolExecutionDefaults.VALIDATE_ARGS,
            "on_missing_tool": ToolExecutionDefaults.ON_MISSING_TOOL.value,
            "max_tool_calls_per_message": ToolExecutionDefaults.MAX_TOOL_CALLS_PER_MESSAGE
        },
        "runner": {
            "max_execution_time": ExecutionDefaults.MAX_EXECUTION_TIME,
            "early_stopping": EarlyStoppingPolicy.FIRST_FINISH.value,
            "max_consecutive_errors": ExecutionDefaults.MAX_CONSECUTIVE_ERRORS,
            "return_intermediate": ExecutionDefaults.RETURN_INTERMEDIATE
        }
    }
    
    return defaults.get(component_type, {})


def get_supported_formats(parser_type: ParserType) -> List[str]:
    """
    Get supported formats for a parser type.
    
    Args:
        parser_type: Type of parser
        
    Returns:
        List of supported format names
    """
    format_map = {
        ParserType.TOOL_CALL: ["tool_calls", "function_calls"],
        ParserType.TEXT: ["react", "text", "structured"],
        ParserType.JSON: ["json", "openai_functions", "agent_format"],
        ParserType.MULTI: ["all"],
        ParserType.CUSTOM: ["custom"]
    }
    
    return format_map.get(parser_type, [])


def get_error_guidance(error_type: str) -> str:
    """
    Get guidance message for an error type.
    
    Args:
        error_type: Type of error
        
    Returns:
        Guidance message string
    """
    guidance_map = {
        "tool_call": ErrorMessages.TOOL_CALL_FORMAT,
        "json": ErrorMessages.JSON_FORMAT,
        "text": ErrorMessages.TEXT_FORMAT,
        "missing_content": ErrorMessages.MISSING_CONTENT,
        "validation": ErrorMessages.VALIDATION_FAILED
    }
    
    return guidance_map.get(error_type, "Please check your input format and try again.")


# =============================================================================
# EXECUTION PHASE CONSTANTS
# =============================================================================

class ExecutionPhase(str, Enum):
    """Phases of plan-and-execute strategy."""
    PLANNING = "planning"
    ALLOCATION = "allocation"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    SYNTHESIS = "synthesis"


# =============================================================================
# TOOL RELATED CONSTANTS
# =============================================================================

class ToolCategory(str, Enum):
    """Categories of tools for phase-based filtering."""
    WORKPLAN = "workplan"
    TOPOLOGY = "topology" 
    IEM = "iem"
    DELEGATION = "delegation"
    WORKSPACE = "workspace"
    DOMAIN = "domain"
    SUMMARIZATION = "summarization"


class ToolNames:
    """Standard tool names to avoid hardcoded strings."""
    
    # WorkPlan tools
    WORKPLAN_CREATE_OR_UPDATE = "workplan.create_or_update"
    WORKPLAN_ASSIGN = "workplan.assign"
    WORKPLAN_MARK = "workplan.mark"
    WORKPLAN_RECORD_EXECUTION = "workplan.record_execution"
    WORKPLAN_INGEST_RESULTS = "workplan.ingest_results"
    WORKPLAN_IS_COMPLETE = "workplan.is_complete"
    WORKPLAN_SUMMARIZE = "workplan.summarize"
    
    # Topology tools
    TOPOLOGY_LIST_ADJACENT = "topology.list_adjacent"
    TOPOLOGY_GET_NODE_CARD = "topology.get_node_card"
    
    # IEM/Delegation tools
    IEM_DELEGATE_TASK = "iem.delegate_task"
    DELEGATE_TASK = "delegate_task"  # Alternative name
    
    # Workspace tools
    WORKSPACE_READ_SUMMARY = "workspace.read_summary"
    
    # Time tools
    TIME_GET_CURRENT = "time.get_current_time"


class ToolKeywords:
    """Keywords used in tool names for filtering."""
    
    # WorkPlan operation keywords
    CREATE = "create"
    UPDATE = "update"
    ASSIGN = "assign"
    MARK = "mark"
    INGEST = "ingest"
    COMPLETE = "complete"
    SUMMARIZE = "summarize"
    
    # Tool name prefixes
    WORKPLAN_PREFIX = "workplan."
    TOPOLOGY_PREFIX = "topology."
    IEM_PREFIX = "iem."
    WORKSPACE_PREFIX = "workspace."


class PhaseToolMapping:
    """Defines which tool categories/keywords are available in each phase."""
    
    PLANNING_KEYWORDS: Set[str] = {ToolKeywords.CREATE, ToolKeywords.UPDATE}
    PLANNING_CATEGORIES: Set[ToolCategory] = {ToolCategory.WORKPLAN, ToolCategory.TOPOLOGY}
    
    ALLOCATION_KEYWORDS: Set[str] = {ToolKeywords.ASSIGN}
    ALLOCATION_CATEGORIES: Set[ToolCategory] = {
        ToolCategory.WORKPLAN, ToolCategory.TOPOLOGY, ToolCategory.IEM, ToolCategory.DELEGATION
    }
    
    EXECUTION_KEYWORDS: Set[str] = set()  # No manual status marking
    EXECUTION_CATEGORIES: Set[ToolCategory] = {ToolCategory.WORKPLAN, ToolCategory.DOMAIN}
    
    MONITORING_KEYWORDS: Set[str] = {
        ToolKeywords.INGEST, ToolKeywords.COMPLETE, ToolKeywords.ASSIGN, ToolKeywords.MARK
    }
    MONITORING_CATEGORIES: Set[ToolCategory] = {
        ToolCategory.WORKPLAN, ToolCategory.IEM, ToolCategory.DELEGATION, ToolCategory.TOPOLOGY
    }
    
    SYNTHESIS_KEYWORDS: Set[str] = {ToolKeywords.SUMMARIZE}
    SYNTHESIS_CATEGORIES: Set[ToolCategory] = {ToolCategory.WORKPLAN, ToolCategory.SUMMARIZATION}
    
    @classmethod
    def get_categories_for_phase(cls, phase: 'ExecutionPhase') -> Set[ToolCategory]:
        """
        Get tool categories allowed for a specific execution phase.
        
        Args:
            phase: The execution phase
            
        Returns:
            Set of tool categories allowed in this phase
        """
        phase_mapping = {
            ExecutionPhase.PLANNING: cls.PLANNING_CATEGORIES,
            ExecutionPhase.ALLOCATION: cls.ALLOCATION_CATEGORIES,
            ExecutionPhase.EXECUTION: cls.EXECUTION_CATEGORIES,
            ExecutionPhase.MONITORING: cls.MONITORING_CATEGORIES,
            ExecutionPhase.SYNTHESIS: cls.SYNTHESIS_CATEGORIES,
        }
        return phase_mapping.get(phase, set())
    
    @classmethod
    def get_keywords_for_phase(cls, phase: 'ExecutionPhase') -> Set[str]:
        """
        Get tool keywords allowed for a specific execution phase.
        
        Args:
            phase: The execution phase
            
        Returns:
            Set of tool keywords allowed in this phase
        """
        phase_mapping = {
            ExecutionPhase.PLANNING: cls.PLANNING_KEYWORDS,
            ExecutionPhase.ALLOCATION: cls.ALLOCATION_KEYWORDS,
            ExecutionPhase.EXECUTION: cls.EXECUTION_KEYWORDS,
            ExecutionPhase.MONITORING: cls.MONITORING_KEYWORDS,
            ExecutionPhase.SYNTHESIS: cls.SYNTHESIS_KEYWORDS,
        }
        return phase_mapping.get(phase, set())
