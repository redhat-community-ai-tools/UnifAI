"""OpenShell Sandbox Exec tool — executes commands in a remote sandbox."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool


class SandboxExecInput(BaseModel):
    """Args schema for the sandbox_exec tool."""
    cmd: str = Field(..., description="Shell command to execute in the sandbox")
    workdir: Optional[str] = Field(None, description="Working directory for the command")


class SandboxExecTool(BaseTool):
    """Executes shell commands inside an OpenShell sandbox via the gRPC SDK.

    Phase 1 scope: gateway connection (config + mTLS certs) and health
    check validation. Sandbox lifecycle (creation, targeting, cleanup)
    will be added in Phase 2.
    """

    name: str = "SandboxExecTool"
    description: str = "Execute a shell command inside an OpenShell sandbox"
    args_schema = SandboxExecInput

    def __init__(
        self,
        *,
        endpoint: str,
        ca_pem: str,
        cert_pem: str,
        key_pem: str,
    ) -> None:
        super().__init__()
        self._endpoint = endpoint
        self._ca_pem = ca_pem
        self._cert_pem = cert_pem
        self._key_pem = key_pem
        self._client = self._build_client()

        translation = str.maketrans(".:- /", "_____")
        safe_endpoint = endpoint.translate(translation)
        self.name = f"sandbox_exec_{safe_endpoint}"
        self.description = (
            f"Execute a shell command inside an OpenShell sandbox "
            f"on gateway {endpoint}."
        )

    def _build_client(self) -> Any:
        """Create a SandboxClient via the ephemeral-tempfile factory."""
        from .client import create_client_from_pem

        return create_client_from_pem(
            self._endpoint,
            ca_pem=self._ca_pem,
            cert_pem=self._cert_pem,
            key_pem=self._key_pem,
        )

    def run(self, *args: Any, **kwargs: Any) -> str:
        """Sandbox exec is not yet available — sandbox targeting deferred to Phase 2."""
        return (
            "ERROR: sandbox_exec is not yet fully operational. "
            "Gateway connection is configured but sandbox lifecycle "
            "(creation, targeting, cleanup) will be added in Phase 2."
        )

    def close(self) -> None:
        """Release the gRPC channel."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __del__(self) -> None:
        self.close()
