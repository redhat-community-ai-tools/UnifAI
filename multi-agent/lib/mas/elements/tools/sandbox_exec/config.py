from typing import Literal, Optional
from pydantic import Field
from mas.elements.tools.common.base_config import BaseToolConfig
from mas.core.field_hints import (
    FileUploadHint,
    SecretHint,
    combine_hints,
)
from .identifiers import Identifier


class SandboxExecToolConfig(BaseToolConfig):
    """Configuration for the OpenShell sandbox execution tool."""

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    gateway_url: str = Field(
        ...,
        description="OpenShell gateway URL (e.g. https://gateway.example.com:443)",
    )

    custom_image: Optional[str] = Field(
        default=None,
        description="Custom container image to use for the sandbox (optional)",
    )

    keep_sandbox: bool = Field(
        default=False,
        description="Keep sandboxes alive between executions for session persistence",
    )

    ca_cert: str = Field(
        ...,
        description="CA certificate for mTLS (PEM format)",
        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.crt,.key"),
            SecretHint(reason="Certificate content should be masked"),
        ),
    )

    tls_cert: str = Field(
        ...,
        description="Client TLS certificate for mTLS (PEM format)",
        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.crt,.key"),
            SecretHint(reason="Certificate content should be masked"),
        ),
    )

    tls_key: str = Field(
        ...,
        description="Client TLS private key for mTLS (PEM format)",
        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.crt,.key"),
            SecretHint(reason="Private key content should be masked"),
        ),
    )
