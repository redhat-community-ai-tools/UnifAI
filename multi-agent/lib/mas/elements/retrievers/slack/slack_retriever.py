import requests
from typing import Any, Optional

from mas.elements.retrievers.common.base_retriever import BaseRetriever
from mas.elements.retrievers.common.protocols import RetrievalIdentity
from pydantic import HttpUrl


class SlackRetriever(BaseRetriever):
    """
    Calls an external Slack-query API to fetch matching messages.

    Depends on ``RetrievalIdentity`` (Protocol) for access control —
    knows nothing about ``ExecutionContext`` or holders.
    """

    def __init__(
        self,
        api_url: HttpUrl,
        top_k_results: int,
        threshold: float,
        identity: Optional[RetrievalIdentity] = None,
    ):
        self.api_url = str(api_url)
        self.top_k = top_k_results
        self.threshold = threshold
        self._identity = identity

    def retrieve(self, query: str) -> Any:
        scope = self._identity.scope if self._identity else "public"
        user_id = self._identity.identity_id if self._identity else ""

        params = {
            "query": query,
            "top_k_results": self.top_k,
            "scope": scope,
            "loggedInUser": user_id,
        }

        resp = requests.get(self.api_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if "search_results" in data:
            data = data["search_results"]
        if isinstance(data, list):
            return [item for item in data if item.get("score", 0.0) >= self.threshold]
        return data
