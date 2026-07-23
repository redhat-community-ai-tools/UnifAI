from typing import Literal, ClassVar, Tuple

from pydantic import Field

from mas.elements.sandboxes.common.base_config import BaseSandboxConfig
from mas.core.field_hints import SecretHint, FileUploadHint, HiddenHint, CardHint, combine_hints
from .identifiers import Identifier


class OpenShellSandboxConfig(BaseSandboxConfig):
    """Configuration for the OpenShell Sandbox."""

    ENCRYPTED_FIELDS: ClassVar[Tuple[str, ...]] = ("ca_cert", "tls_cert", "tls_key")

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    gateway_url: str = Field(
        ...,
        description="OpenShell gateway endpoint (host:port or https://host:port)",
        json_schema_extra=CardHint(contexts=["builtin", "custom"]).to_hints(),
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
    workdir: str = Field(
        default="/sandbox",
        description="Default working directory for commands executed in the sandbox.",
        json_schema_extra=HiddenHint(reason="Internal: derived from container image WORKDIR").to_hints(),
    )
