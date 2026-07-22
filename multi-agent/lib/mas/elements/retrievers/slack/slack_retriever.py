import requests
from typing import Any, Optional

from mas.elements.retrievers.common.base_retriever import BaseRetriever
from mas.elements.retrievers.common.protocols import RetrievalIdentity
from pydantic import HttpUrl
from global_utils.constants import INTERNAL_AUTH_HEADER



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
        timeout: float = 30.0,
        identity: Optional[RetrievalIdentity] = None,
    ):
        self.api_url = str(api_url)
        self.top_k = top_k_results
        self.threshold = threshold
        self.timeout = timeout
        self._identity = identity

    _AUTH_HEADER = INTERNAL_AUTH_HEADER

    def retrieve(self, query: str) -> Any:
        user_id = self._identity.identity_id if self._identity else ""

        params = {
            "query": query,
            "top_k_results": self.top_k,
        }

        headers = {self._AUTH_HEADER: user_id} if user_id else {}

        resp = requests.get(
            self.api_url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if "search_results" in data:
            data = data["search_results"]
        if isinstance(data, list):
            return [item for item in data if item.get("score", 0.0) >= self.threshold]
        return data
