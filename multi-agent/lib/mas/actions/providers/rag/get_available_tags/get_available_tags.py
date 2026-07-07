from typing import List, Optional, Dict, Any
from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.elements.providers.rag_client.config import RagProviderConfig
from mas.elements.providers.rag_client.rag_provider_factory import RagProviderFactory
from mas.elements.providers.rag_client.identifiers import Identifier as RagProviderIdentifier
from mas.elements.retrievers.docs_rag.identifiers import Identifier as RetrieverIdentifier
from mas.core.enums import ResourceCategory


class GetAvailableTagsInput(BaseActionInput):
    """Input for fetching available tags"""
    limit: int = 50
    cursor: Optional[str] = None
    search_regex: Optional[str] = None


class GetAvailableTagsOutput(BaseActionOutput):
    """Output for available tags"""
    tags: List[str] = []
    next_cursor: Optional[str] = None
    has_more: bool = False
    total: int = 0


class GetAvailableTagsAction(BaseAction):
    """
    Fetches available tags from RAG service (sync).
    """

    uid = "rag.get_available_tags"
    name = "get_available_tags"
    description = "Retrieve available tags from the RAG service"
    action_type = ActionType.DISCOVERY
    input_schema = GetAvailableTagsInput
    output_schema = GetAvailableTagsOutput
    version = "1.0.0"
    tags = {"rag", "discovery", "tags"}
    elements = {(ResourceCategory.PROVIDER.value, RagProviderIdentifier.TYPE),
                (ResourceCategory.RETRIEVER.value, RetrieverIdentifier.TYPE)}

    def execute(
            self,
            input_data: GetAvailableTagsInput,
            context: Optional[Dict[str, Any]] = None
    ) -> GetAvailableTagsOutput:
        """Execute tags discovery (sync)."""
        try:
            config = RagProviderConfig()
            factory = RagProviderFactory()
            provider = factory.create(config)

            response = provider.get_available_tags(
                limit=input_data.limit,
                cursor=input_data.cursor,
                search_regex=input_data.search_regex,
            )

            return GetAvailableTagsOutput(
                success=True,
                message=f"Found {response.total} tags",
                tags=[t.label for t in response.options],
                next_cursor=response.nextCursor,
                has_more=response.hasMore,
                total=response.total
            )

        except Exception as e:
            return GetAvailableTagsOutput(
                success=False,
                message=f"Failed to retrieve tags: {str(e)}",
                tags=[],
                total=0
            )
