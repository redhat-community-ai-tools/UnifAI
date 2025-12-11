import time
from typing import Optional, Dict, Any
from pydantic import HttpUrl
from actions.common.base_action import BaseAction
from actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from elements.providers.dataflow_client.client import DataflowClient, DataflowClientError
from elements.providers.dataflow_client.identifiers import Identifier
from core.enums import ResourceCategory


class ValidateConnectionInput(BaseActionInput):
    """Input for Dataflow connection validation"""
    base_url: HttpUrl


class ValidateConnectionOutput(BaseActionOutput):
    """Output for Dataflow connection validation"""
    is_reachable: bool = False
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    """
    Validates Dataflow server connection.
    """

    uid = "dataflow.validate_connection"
    name = "validate_connection"
    description = "Validate that the Dataflow server endpoint is reachable"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "1.0.0"
    tags = {"dataflow", "validation", "connectivity"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidateConnectionOutput:
        """Execute connection validation (sync)."""
        start_time = time.time()

        try:
            with DataflowClient(input_data.base_url, timeout=10.0) as client:
                health = client.health_check()

            response_time = (time.time() - start_time) * 1000

            return ValidateConnectionOutput(
                success=health.is_healthy,
                message=health.message,
                is_reachable=health.is_healthy,
                response_time_ms=response_time
            )

        except DataflowClientError as e:
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {str(e)}",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {str(e)}",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000
            )

