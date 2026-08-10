"""Factory for creating execution handlers.

Separated from ``handlers.py`` so that it can import concrete handler
implementations (including ``HITLExecutionHandler``) without circular
dependencies — ``handlers.py`` defines the ABCs that those concrete
handlers inherit from.
"""

from typing import Optional

from ..hitl_config import HITLHandlerConfig
from .executor import AgentActionExecutor
from .handlers import (
    AutoExecutionHandler,
    ExecutionHandler,
    ExecutionMode,
    GuidedExecutionHandler,
)
from .hitl_handler import HITLExecutionHandler


class ExecutionHandlerFactory:
    """Factory for creating execution handlers.

    Provides a clean way to create handlers without tight coupling
    to concrete implementations.
    """

    @staticmethod
    def create(
        mode: ExecutionMode,
        action_executor: AgentActionExecutor,
        hitl_config: Optional[HITLHandlerConfig] = None,
    ) -> ExecutionHandler:
        """Create an execution handler for the specified mode.

        Args:
            mode: Execution mode.
            action_executor: Action executor instance.
            hitl_config: Typed HITL configuration (required when mode is HITL).

        Returns:
            Appropriate execution handler instance.

        Raises:
            ValueError: If mode is not supported or HITL config is missing.
        """
        if mode == ExecutionMode.AUTO:
            return AutoExecutionHandler(action_executor)
        elif mode == ExecutionMode.GUIDED:
            return GuidedExecutionHandler(action_executor)
        elif mode == ExecutionMode.HITL:
            if hitl_config is None:
                raise ValueError(
                    "HITLHandlerConfig is required for HITL execution mode"
                )
            return HITLExecutionHandler(
                action_executor,
                gate=hitl_config.gate,
                policy=hitl_config.policy,
                tool_registry=hitl_config.tool_registry,
                node_uid=hitl_config.node_uid,
                node_display_name=hitl_config.node_display_name,
                session_id=hitl_config.session_id,
            )
        else:
            raise ValueError(f"Unsupported execution mode: {mode}")

    @staticmethod
    def get_supported_modes():
        return [ExecutionMode.AUTO, ExecutionMode.GUIDED, ExecutionMode.HITL]
