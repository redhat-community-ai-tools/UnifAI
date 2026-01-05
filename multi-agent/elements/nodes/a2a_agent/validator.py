"""
elements/nodes/a2a_agent/validator.py

Validator for A2A Agent Node - checks endpoint reachability using A2AClient.
"""

import anyio
from concurrent.futures import CancelledError
from typing import List, Dict

from global_utils.utils.async_bridge import get_async_bridge
from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ElementValidationResult,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from elements.providers.a2a_client import A2AClient
from core.ref.models import Ref


class A2AAgentNodeValidator(BaseElementValidator):
    """
    Validates A2A Agent Node configuration.
    
    Checks:
    - A2A agent endpoint connectivity
    - Ability to fetch agent card from the server
    - Retriever dependency (if configured)
    """

    def validate(
        self,
        config: A2AAgentNodeConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate A2A agent node config.
        
        Synchronous method - runs async checks internally using AsyncBridge.
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []
        checked_dependencies: Dict[str, ElementValidationResult] = {}

        try:
            with get_async_bridge() as bridge:
                bridge.run(self._check_connection(config, context, messages))
        except (CancelledError, TimeoutError) as e:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                str(e),
                field="base_url",
            ))

        # Check retriever dependency (optional)
        if config.retriever:
            retriever_rid = self._extract_rid(config.retriever)
            self._check_dependency(
                context, retriever_rid, "retriever", messages, checked_dependencies
            )

        return self._build_report(
            messages=messages,
            checked_dependencies=checked_dependencies,
        )

    async def _check_connection(
        self,
        config: A2AAgentNodeConfig,
        context: ValidationContext,
        messages: List[ValidationMessage],
    ) -> None:
        """
        Async A2A connection check using A2AClient.
        
        Uses anyio.fail_after INSIDE the async function for timeout control.
        """
        try:
            with anyio.fail_after(context.timeout_seconds):
                async with A2AClient(
                    base_url=config.base_url,
                ) as client:
                    # Agent card is fetched during __aenter__
                    _ = client.agent_card
            
            # Connection successful
            messages.append(self._info(
                "CONNECTION_OK",
                f"Successfully connected to A2A agent at {config.base_url}",
                field="base_url",
            ))

        except TimeoutError:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="base_url",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {str(e)}",
                field="base_url",
            ))

    @staticmethod
    def _extract_rid(ref_obj) -> str:
        """Extract rid string from Ref or string."""
        if isinstance(ref_obj, Ref):
            return ref_obj.ref
        return str(ref_obj)
