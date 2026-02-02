from typing import Dict, List, Optional
from elements.retrievers.common.base_retriever import BaseRetriever
from elements.providers.dataflow_client.config import DataflowProviderConfig
from elements.providers.dataflow_client.dataflow_provider_factory import DataflowProviderFactory
from core.context import get_current_context


class DocsDataflowRetriever(BaseRetriever):
    """
    Retrieves document passages via Dataflow vector database.
    """

    def __init__(
            self,
            top_k_results: int,
            threshold: float,
            timeout: float = 30.0,
            docs: Optional[List[Dict]] = None,
            tags: Optional[List[str]] = None,
    ):
        self.threshold = threshold
        self.docs = docs
        self.tags = tags
        config = DataflowProviderConfig(
            top_k=top_k_results,
            timeout=timeout,
        )
        factory = DataflowProviderFactory()
        self._provider = factory.create(config)

    def retrieve(self, query: str) -> List[dict]:
        context = get_current_context()

        # Extract document IDs from docs list
        doc_ids = [doc['id'] for doc in self.docs] if self.docs else None

        response = self._provider.query(
            query=query,
            scope=context.scope,
            logged_in_user=context.logged_in_user,
            doc_ids=doc_ids,
            tags=self.tags,
        )

        return [
            match.model_dump()
            for match in response.matches
            if match.score >= self.threshold
        ]
