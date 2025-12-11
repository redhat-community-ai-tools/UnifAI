from typing import List, Optional, Dict, Any
from actions.common.base_action import BaseAction
from actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from elements.providers.dataflow_client.config import DataflowProviderConfig
from elements.providers.dataflow_client.dataflow_provider_factory import DataflowProviderFactory
from elements.providers.dataflow_client.identifiers import Identifier as DataFlowProviderIdentifier
from elements.retrievers.docs_dataflow.identifiers import Identifier as RetrieverIdentifier
from core.enums import ResourceCategory


class GetAvailableDocsInput(BaseActionInput):
    """Input for fetching available documents"""
    limit: int = 50
    cursor: Optional[str] = None
    search_regex: Optional[str] = None


class GetAvailableDocsOutput(BaseActionOutput):
    """Output for available documents"""
    documents: List[Dict[str, Any]] = []
    next_cursor: Optional[str] = None
    has_more: bool = False
    total: int = 0


class GetAvailableDocsAction(BaseAction):
    """
    Fetches available documents from Dataflow service (sync).
    """

    uid = "dataflow.get_available_docs"
    name = "get_available_docs"
    description = "Retrieve available document sources from the Dataflow service"
    action_type = ActionType.DISCOVERY
    input_schema = GetAvailableDocsInput
    output_schema = GetAvailableDocsOutput
    version = "1.0.0"
    tags = {"dataflow", "discovery", "docs", "documents"}
    elements = {(ResourceCategory.PROVIDER.value, DataFlowProviderIdentifier.TYPE),
                (ResourceCategory.RETRIEVER.value, RetrieverIdentifier.TYPE)}

    def execute(
            self,
            input_data: GetAvailableDocsInput,
            context: Optional[Dict[str, Any]] = None
    ) -> GetAvailableDocsOutput:
        """Execute docs discovery (sync)."""
        try:
            config = DataflowProviderConfig()
            factory = DataflowProviderFactory()
            provider = factory.create(config)

            response = provider.get_available_docs(
                limit=input_data.limit,
                cursor=input_data.cursor,
                search_regex=input_data.search_regex,
            )

            return GetAvailableDocsOutput(
                success=True,
                message=f"Found {response.total} documents",
                documents=[doc.model_dump() for doc in response.documents],
                next_cursor=response.nextCursor,
                has_more=response.hasMore,
                total=response.total
            )

        except Exception as e:
            return GetAvailableDocsOutput(
                success=False,
                message=f"Failed to retrieve documents: {str(e)}",
                documents=[],
                total=0
            )
