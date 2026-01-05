"""
elements/retrievers/docs_dataflow/validator.py

Validator for DocsDataflow Retriever - checks Dataflow service health.
"""

from typing import List

from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.retrievers.docs_dataflow.config import DocsDataflowRetrieverConfig
from elements.providers.dataflow_client.config import DataflowProviderConfig
from elements.providers.dataflow_client.client import (
    DataflowClient,
    DataflowClientError,
    DataflowConnectionError,
)


class DocsDataflowRetrieverValidator(BaseElementValidator):
    """
    Validates DocsDataflow Retriever configuration.
    
    Checks:
    - Dataflow service reachability
    - Dataflow service health
    """

    def validate(
        self,
        config: DocsDataflowRetrieverConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate DocsDataflow Retriever config.
        
        The retriever uses the default Dataflow service URL.
        We check if that service is healthy.
        
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        # Get default dataflow URL from provider config
        provider_config = DataflowProviderConfig()
        base_url = provider_config.base_url

        try:
            with DataflowClient(
                base_url=base_url,
                timeout=context.timeout_seconds,
            ) as client:
                health = client.health_check()

            if health.is_healthy:
                messages.append(self._info(
                    "CONNECTION_OK",
                    f"Dataflow service is healthy at {base_url}",
                ))
            else:
                messages.append(self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    f"Dataflow service unhealthy: {health.message}",
                ))

        except DataflowConnectionError as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Cannot connect to Dataflow service: {str(e)}",
            ))
        except DataflowClientError as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Dataflow error: {str(e)}",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Unexpected error: {type(e).__name__}",
            ))

        return self._build_report(messages=messages)

