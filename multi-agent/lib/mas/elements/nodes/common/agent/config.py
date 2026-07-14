"""
Agent system configuration classes and utilities.

This module provides configuration dataclasses for controlling all aspects
of agent behavior including strategy selection, execution modes, error handling,
and performance limits.

Design Principles:
- Centralized Configuration: All agent config in one place
- Type Safety: Use enums and proper types for validation
- Reasonable Defaults: Sensible defaults for quick setup
- Extensibility: Easy to add new configuration options
"""

from dataclasses import dataclass
from typing import Optional

from .constants import (
    ExecutionDefaults, EarlyStoppingPolicy
)
from .execution.handlers import ExecutionMode
from .hitl_config import HITLHandlerConfig


@dataclass
class AgentConfig:
    """
    Configuration for agent execution.
    
    Controls execution behavior, error handling, and performance limits.
    Strategy is passed as an object directly, not configured here.
    
    Example:
        config = AgentConfig(
            execution_mode=ExecutionMode.GUIDED,
            max_execution_time=300.0,
            return_intermediate=True
        )
        
        strategy = ReActStrategy(llm_chat=node.chat, tools=tools)
        result = agent.run_agent(messages, strategy, config=config)
    """
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    
    max_execution_time: Optional[float] = ExecutionDefaults.MAX_EXECUTION_TIME
    max_actions_per_minute: Optional[int] = ExecutionDefaults.MAX_ACTIONS_PER_MINUTE
    
    early_stopping: str = EarlyStoppingPolicy.FIRST_FINISH.value
    return_intermediate: bool = ExecutionDefaults.RETURN_INTERMEDIATE
    
    executor_config: Optional['ExecutorConfig'] = None

    hitl_config: Optional[HITLHandlerConfig] = None


# Future extension examples for when we add more config classes:

# @dataclass
# class StrategyConfig:
#     """Configuration for specific strategies."""
#     pass

# @dataclass  
# class ExecutionConfig:
#     """Configuration for execution behavior."""
#     pass

# @dataclass
# class ParserConfig:
#     """Configuration for output parsing."""
#     pass

# class AgentConfigBuilder:
#     """Builder pattern for complex configurations."""
#     pass

# class ConfigTemplates:
#     """Pre-built configuration templates for common use cases."""
#     
#     @staticmethod
#     def development() -> AgentConfig:
#         """Development-friendly config with verbose output."""
#         return AgentConfig(
#             execution_mode=ExecutionMode.GUIDED,
#             return_intermediate=True,
#             reflect_on_errors=True
#         )
#     
#     @staticmethod
#     def production() -> AgentConfig:
#         """Production config optimized for performance."""
#         return AgentConfig(
#             execution_mode=ExecutionMode.AUTO,
#             return_intermediate=False,
#             max_execution_time=60.0
#         )
#     
#     @staticmethod
#     def safe() -> AgentConfig:
#         """Safety-first config with human oversight."""
#         return AgentConfig(
#             execution_mode=ExecutionMode.GUIDED,
#             validate_tools=True,
#             max_steps=5,
#             early_stopping=EarlyStoppingPolicy.FIRST_ERROR.value
#         )