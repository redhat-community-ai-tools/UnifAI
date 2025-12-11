from typing import Literal, Optional, List
from pydantic import Field
from elements.retrievers.common.base_config import BaseRetrieverConfig
from core.field_hints import ActionHint, HintType, SelectionType
from .identifiers import Identifier


class DocsDataflowRetrieverConfig(BaseRetrieverConfig):
    """
    Retrieves document passages via Dataflow service.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    top_k_results: int = Field(
        default=3,
        ge=1,
        description="Number of top document passages to return"
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

    doc_ids: Optional[List[str]] = Field(
        default=None,
        description="Filter results to specific document IDs",
        json_schema_extra=ActionHint(
            action_uid="dataflow.get_available_docs",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.MANUAL,
            field_mapping="documents",
            label_field="name",
            value_field="id",
            multi_select=True,
            pagination=True,
            search=True,
        ).to_hints()
    )

    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter results by tags",
        json_schema_extra=ActionHint(
            action_uid="dataflow.get_available_tags",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.MANUAL,
            field_mapping="tags",
            multi_select=True,
            pagination=True,
            search=True,
        ).to_hints()
    )
