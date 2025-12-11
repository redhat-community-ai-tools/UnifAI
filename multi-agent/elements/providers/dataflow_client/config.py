from typing import Literal
from pydantic import Field, HttpUrl
from elements.providers.common.base_config import ProviderBaseConfig
from core.field_hints import ActionHint, HintType
from .identifiers import Identifier


class DataflowProviderConfig(ProviderBaseConfig):
    """
    Configuration for Dataflow service client.
    Connects to a Dataflow server for vector database queries and document retrieval.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    base_url: HttpUrl = Field(
        default="http://unifai-dataflow-server:13456",
        description="Base URL of the Dataflow service",
        json_schema_extra=ActionHint(
            action_uid="dataflow.validate_connection",
            hint_type=HintType.VALIDATE,
            field_mapping="is_reachable"
        ).to_hints()
    )

    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of top results to return from vector queries"
    )

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds"
    )

