from typing import Literal

from pydantic import Field

from mas.elements.sandboxes.common.base_config import BaseSandboxConfig
from mas.core.field_hints import SecretHint, FileUploadHint, combine_hints
from .identifiers import Identifier


class OpenShellSandboxConfig(BaseSandboxConfig):
    """Configuration for the OpenShell Sandbox."""

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    gateway_url: str = Field(
        ...,
        description="OpenShell gateway endpoint (host:port or https://host:port)",
    )
    ca_cert: str = Field(
        ...,
        description="CA certificate (PEM)",
        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.crt", validate_format="pem"),
            SecretHint(reason="Certificate content should be masked", allow_reveal=False),
        ),
    )
    tls_cert: str = Field(
        ...,
        description="Client TLS certificate (PEM)",
        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.crt", validate_format="pem"),
            SecretHint(reason="Certificate content should be masked", allow_reveal=False),
        ),
    )
    tls_key: str = Field(
        ...,
        description="Client TLS private key (PEM)",
        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.key", validate_format="pem"),
            SecretHint(reason="Private key should be masked", allow_reveal=False),
        ),
    )
    keep_sandbox: bool = Field(
        default=False,
        description="Keep the sandbox container running after use.",
    )
