from typing import Literal
from pydantic import Field
from elements.tools.common.base_config import BaseToolConfig
from core.field_hints import SecretHint
from .identifiers import Identifier


class OcExecToolConfig(BaseToolConfig):
    """Configuration for OpenShift CLI tool."""
    
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    
    server: str = Field(
        ..., 
        description="OpenShift API server URL (e.g., https://api.cluster.example.com:6443)"
    )
    
    token: str = Field(
        ..., 
        description="OpenShift authentication token",
        json_schema_extra=SecretHint(
            reason="Token credential should be masked",
            allow_reveal=False
        ).to_hints()
    )
    
    skip_tls_verify: bool = Field(
        default=False,
        description="Skip TLS certificate verification"
    )
