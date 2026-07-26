from typing import Dict, List, Literal, Optional
from pydantic import Field
from mas.elements.retrievers.common.base_config import BaseRetrieverConfig
from mas.core.field_hints import ActionHint, HintType, SelectionType, CardHint
from .identifiers import Identifier


class DocsRagRetrieverConfig(BaseRetrieverConfig):
    """
    Retrieves document passages via RAG service.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    top_k_results: int = Field(
        default=3,
        ge=1,
        description="Number of top document passages to return",
        json_schema_extra=CardHint(contexts=["builtin", "custom"]).to_hints(),
    )

    threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score to include a passage"
    )

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds"
    )

    docs: Optional[List[Dict]] = Field(
        default=None,
        description="Filter results to specific documents",
        json_schema_extra=ActionHint(
            action_uid="rag.get_available_docs",
            display_name="documents",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.MANUAL,
            field_mapping="documents",
            display_field="name",
            multi_select=True,
            pagination=True,
            search=True,
        ).to_hints()
    )

    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter results by tags",
        json_schema_extra=ActionHint(
            action_uid="rag.get_available_tags",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.MANUAL,
            field_mapping="tags",
            multi_select=True,
            pagination=True,
            search=True,
        ).to_hints()
    )
