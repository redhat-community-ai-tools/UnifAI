from typing import Dict, List, Optional

from mas.elements.retrievers.common.base_retriever import BaseRetriever
from mas.elements.retrievers.common.protocols import RetrievalIdentity
from mas.elements.providers.rag_client.config import RagProviderConfig
from mas.elements.providers.rag_client.rag_provider_factory import RagProviderFactory


class DocsRagRetriever(BaseRetriever):
    """
    Retrieves document passages via RAG vector database.

    Depends on ``RetrievalIdentity`` (Protocol) for access control —
    knows nothing about ``ExecutionContext`` or holders.
    """

    def __init__(
            self,
            top_k_results: int,
            threshold: float,
            timeout: float = 30.0,
            docs: Optional[List[Dict]] = None,
            tags: Optional[List[str]] = None,
            identity: Optional[RetrievalIdentity] = None,
    ):
        self.threshold = threshold
        self.docs = docs
        self.tags = tags
        self._identity = identity
        config = RagProviderConfig(
            top_k=top_k_results,
            timeout=timeout,
        )
        factory = RagProviderFactory()
        self._provider = factory.create(config)

    def retrieve(self, query: str) -> List[dict]:
        scope = self._identity.scope if self._identity else "public"
        user_id = self._identity.identity_id if self._identity else ""
        doc_ids = [doc['id'] for doc in self.docs] if self.docs else None

        response = self._provider.query(
            query=query,
            scope=scope,
            logged_in_user=user_id,
            doc_ids=doc_ids,
            tags=self.tags,
        )

        return [
            match.model_dump()
            for match in response.matches
            if match.score >= self.threshold
        ]
