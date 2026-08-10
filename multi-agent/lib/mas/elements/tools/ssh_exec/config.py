from typing import Literal
from pydantic import Field
from mas.elements.tools.common.base_config import BaseToolConfig
from mas.core.field_hints import SecretHint, CardHint, CardContext
from .identifiers import Identifier


class SshExecToolConfig(BaseToolConfig):
    """
    Configuration for the SSH-execution tool.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    host: str = Field(
        ...,
        description="IP or DNS name of the target VM",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    port: int = Field(22, description="SSH port")
    username: str = Field(
        ...,
        description="SSH user name",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    password: str = Field(
        ..., 
        description="SSH password",
        json_schema_extra=SecretHint(
            reason="Password credential should be masked",
            allow_reveal=False
        ).to_hints()
    )
