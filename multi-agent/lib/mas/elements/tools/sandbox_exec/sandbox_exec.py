from typing import Any, Optional
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool


class SandboxCommand(BaseModel):
    """Input schema for sandbox command execution."""
    cmd: str = Field(..., description="Shell command to run inside the sandbox")


class SandboxExecTool(BaseTool):
    """Execute shell commands in an isolated OpenShell sandbox container.

    The gateway is a user-provisioned VM that can host multiple sandbox
    containers concurrently.  This tool lazily creates one sandbox on
    first use; when ``keep_sandbox`` is enabled the same sandbox is
    reused across calls, otherwise a fresh one is created each time.
    Heavy dependencies (``openshell``, ``grpcio``) are imported lazily
    to avoid startup failures when the packages are not installed.
    """

    name: str = "SandboxExecTool"
    description: str = "Execute a shell command inside a secure sandbox container"
    args_schema = SandboxCommand

    def __init__(
        self,
        *,
        gateway_url: str,
        ca_cert: str,
        tls_cert: str,
        tls_key: str,
        custom_image: Optional[str] = None,
        keep_sandbox: bool = False,
    ):
        super().__init__()
        self._gateway_url = gateway_url
        self._ca_cert = ca_cert
        self._tls_cert = tls_cert
        self._tls_key = tls_key
        self._custom_image = custom_image
        self._keep_sandbox = keep_sandbox
        self._sandbox: Any = None

        translation = str.maketrans(".:- /", "_____")
        safe_url = gateway_url.translate(translation)
        self.name = f"sandbox_exec_{safe_url}"

        image_line = f"Image: {custom_image}" if custom_image else "Image: default"
        persistence = (
            "Sandbox reuse: ON — commands run in the same sandbox across calls"
            if keep_sandbox
            else "Sandbox reuse: OFF — each call creates a fresh sandbox"
        )
        self.description = (
            f"Execute shell commands in an isolated OpenShell sandbox container.\n\n"
            f"The gateway at {gateway_url} is a VM that hosts multiple "
            f"sandbox containers. Each sandbox is an independent, secure "
            f"container — separate agents and workflow executions each get "
            f"their own.\n\n"
            f"{image_line}\n"
            f"{persistence}\n\n"
            f"Provide a shell command and it will run inside a sandbox "
            f"container on this gateway."
        )

    def _get_or_create_sandbox(self) -> Any:
        """Lazily create or return the existing sandbox."""
        if self._sandbox is not None:
            return self._sandbox

        try:
            from openshell import OpenShell
        except ImportError as exc:
            raise RuntimeError(
                "The 'openshell' package is required for SandboxExecTool. "
                "Install it with: pip install 'openshell>=0.0.59'"
            ) from exc

        client = OpenShell(
            gateway_url=self._gateway_url,
            ca_cert=self._ca_cert,
            tls_cert=self._tls_cert,
            tls_key=self._tls_key,
        )

        create_kwargs: dict[str, Any] = {}
        if self._custom_image:
            create_kwargs["image"] = self._custom_image

        sandbox = client.sandbox.create(**create_kwargs)
        if self._keep_sandbox:
            self._sandbox = sandbox
        return sandbox

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)

        try:
            sandbox = self._get_or_create_sandbox()
            result = sandbox.exec(inp.cmd)
            return result.stdout.strip() if result.stdout else (
                f"STDERR:\n{result.stderr.strip()}" if result.stderr else "(no output)"
            )
        except RuntimeError:
            raise
        except Exception as e:
            return f"ERROR: Failed to execute command in sandbox: {e}"

    def close(self) -> None:
        """Terminate the sandbox if one is active."""
        if self._sandbox is not None:
            try:
                self._sandbox.terminate()
            except Exception:
                pass
            self._sandbox = None

    def __del__(self) -> None:
        self.close()
