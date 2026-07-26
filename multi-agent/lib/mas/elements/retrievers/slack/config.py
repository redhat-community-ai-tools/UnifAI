from typing import Literal
from .identifiers import Identifier
from pydantic import Field, HttpUrl
from mas.elements.retrievers.common.base_config import BaseRetrieverConfig
from mas.core.field_hints import HiddenHint, CardHint, CardContext


class SlackRetrieverConfig(BaseRetrieverConfig):
    """
    Retrieves messages from Slack via an API endpoint.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    api_url: HttpUrl = Field(
        HttpUrl("http://unifai-rag-server:13456/api/slack/query.match"),
        # default_factory=lambda: HttpUrl(
            # "https://unifai-rag-server-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com/api/slack/query.match"),
        description="URL for retrieving slack messages from the API",
        json_schema_extra=HiddenHint(reason="UI hint to hide this value").to_hints()
    )
    top_k_results: int = Field(
        3, ge=1,
        description="Number of top Slack messages to return",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    threshold: float = Field(
        0.3, ge=0.0, le=1.0,
        description="Minimum relevance score to include a message"
    )
