"""Sandbox Exec Tool — execute shell commands in OpenShell sandbox containers.

Follows the same ``{cmd: str}`` pattern as ``SshExecTool``.  The tool
handles sandbox lifecycle internally: lazy creation on first use,
reconnection via server-side label filtering, and cleanup on close.

Uses the OpenShell Python SDK for ``get``, ``exec``, ``delete``, and
``wait_ready``.  Bypasses the SDK via the gRPC stub for ``create``
(with name + labels) and ``list`` (with label_selector) because the
Python SDK does not yet expose those parameters.

Heavy dependencies (``openshell``, ``grpcio``) are imported lazily so
the tool can be registered without them installed.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)


class SandboxCommand(BaseModel):
    """Input schema for sandbox command execution."""

    cmd: str = Field(..., description="Shell command to run inside the sandbox")
    workdir: Optional[str] = Field(
        default=None,
        description="Working directory for the command (e.g. '/workspace')",
    )
    env: Optional[Dict[str, str]] = Field(
        default=None,
        description="Environment variables to inject for this command",
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="Command timeout in seconds (default: no limit)",
    )


class _GatewayHelper:
    """Wraps gRPC calls the Python SDK doesn't expose yet.

    Isolates ``SandboxClient._stub`` access so the rest of the tool
    uses the public SDK API.  Replaceable once the SDK adds ``name``,
    ``labels``, and ``label_selector`` parameters.
    """

    def __init__(self, client: Any) -> None:
        self._stub = client._stub
        self._timeout = client._timeout

    def create(self, spec: Any, name: str, labels: Dict[str, str]) -> Any:
        """CreateSandbox with caller-supplied *name* and *labels*."""
        from openshell._proto import openshell_pb2

        response = self._stub.CreateSandbox(
            openshell_pb2.CreateSandboxRequest(
                spec=spec, name=name, labels=labels,
            ),
            timeout=self._timeout,
        )
        return self._to_ref(response.sandbox)

    def list_sandboxes(self, label_selector: str = "") -> List[Any]:
        """ListSandboxes with optional server-side *label_selector* filter."""
        from openshell._proto import openshell_pb2

        response = self._stub.ListSandboxes(
            openshell_pb2.ListSandboxesRequest(label_selector=label_selector),
            timeout=self._timeout,
        )
        return [self._to_ref(s) for s in response.sandboxes]

    @staticmethod
    def _to_ref(sandbox: Any) -> Any:
        """Convert protobuf ``Sandbox`` to ``SandboxRef``."""
        from openshell import SandboxRef, SandboxStatusRef

        status = sandbox.status if sandbox.HasField("status") else None
        return SandboxRef(
            id=sandbox.metadata.id if sandbox.metadata else "",
            name=sandbox.metadata.name if sandbox.metadata else "",
            status=SandboxStatusRef(
                phase=status.phase if status else 0,
                current_policy_version=(
                    status.current_policy_version if status else 0
                ),
            ),
        )


class SandboxExecTool(BaseTool):
    """Execute shell commands in an isolated OpenShell sandbox container.

    Behaves like ``SshExecTool``: the LLM sends ``{cmd, workdir?, env?,
    timeout_seconds?}`` and the tool manages the sandbox lifecycle
    internally (create on first use, reconnect on Temporal rebuild,
    delete on close).
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
    ) -> None:
        super().__init__()
        self._gateway_url = gateway_url
        self._ca_cert = ca_cert
        self._tls_cert = tls_cert
        self._tls_key = tls_key
        self._custom_image = custom_image
        self._keep_sandbox = keep_sandbox

        self._session_id: str = ""
        self._agent_id: str = ""
        self._client: Any = None
        self._gateway: Optional[_GatewayHelper] = None
        self._tmp_dir: Optional[str] = None
        self._active_sandbox: Any = None

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
            f"Execute shell commands in an isolated OpenShell sandbox "
            f"container.\n\n"
            f"The gateway at {gateway_url} is a VM that hosts multiple "
            f"sandbox containers. Each sandbox is an independent, secure "
            f"container — separate agents and workflow executions each get "
            f"their own.\n\n"
            f"{image_line}\n"
            f"{persistence}\n\n"
            f"Provide a shell command and it will run inside a sandbox "
            f"container on this gateway. You can optionally specify a "
            f"working directory, environment variables, and a timeout."
        )

    # ------------------------------------------------------------------
    # Context binding
    # ------------------------------------------------------------------

    def bind_context(self, *, session_id: str = "", agent_id: str = "") -> None:
        """Late-bind execution context for deterministic sandbox naming."""
        self._session_id = session_id
        self._agent_id = agent_id

    # ------------------------------------------------------------------
    # Deterministic naming & labels
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize(value: str) -> str:
        """Make a string DNS-label safe."""
        return re.sub(r"[^a-z0-9]", "-", value.lower()).strip("-")

    @property
    def _sandbox_name(self) -> str:
        if self._session_id and self._agent_id:
            safe_session = self._sanitize(self._session_id[:12])
            safe_agent = self._sanitize(self._agent_id[:12])
            return f"sb-{safe_session}-{safe_agent}"
        return f"sb-{uuid4().hex[:16]}"

    @property
    def _sandbox_labels(self) -> Dict[str, str]:
        return {
            "unifai.session": self._session_id[:12],
            "unifai.agent": self._agent_id[:12],
        }

    @property
    def _label_selector(self) -> str:
        return ",".join(f"{k}={v}" for k, v in self._sandbox_labels.items())

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def _ensure_client(self) -> None:
        """Lazily create ``SandboxClient`` + ``_GatewayHelper``."""
        if self._client is not None:
            return

        try:
            from openshell import SandboxClient, TlsConfig
        except ImportError as exc:
            raise RuntimeError(
                "The 'openshell' package is required for SandboxExecTool. "
                "Install it with: pip install 'openshell>=0.0.59'"
            ) from exc

        self._tmp_dir = tempfile.mkdtemp(prefix="sandbox_tls_")
        ca_path = Path(self._tmp_dir) / "ca.crt"
        cert_path = Path(self._tmp_dir) / "tls.crt"
        key_path = Path(self._tmp_dir) / "tls.key"
        ca_path.write_text(self._ca_cert)
        cert_path.write_text(self._tls_cert)
        key_path.write_text(self._tls_key)

        parsed = urlparse(self._gateway_url)
        endpoint = f"{parsed.hostname}:{parsed.port or 443}"

        self._client = SandboxClient(
            endpoint,
            tls=TlsConfig(
                ca_path=ca_path, cert_path=cert_path, key_path=key_path,
            ),
            timeout=300.0,
        )
        self._gateway = _GatewayHelper(self._client)

    # ------------------------------------------------------------------
    # Sandbox lifecycle (hidden from LLM)
    # ------------------------------------------------------------------

    def _find_my_sandbox(self) -> Any:
        """Find the sandbox for this agent session via server-side label filter."""
        assert self._gateway is not None
        results = self._gateway.list_sandboxes(label_selector=self._label_selector)
        for ref in results:
            if ref.status.phase == 2:
                return ref
        return None

    def _get_or_create_sandbox(self) -> Any:
        """Return the cached sandbox, reconnect by labels, or create a new one."""
        if self._active_sandbox is not None:
            return self._active_sandbox

        self._ensure_client()

        found = self._find_my_sandbox()
        if found is not None:
            self._active_sandbox = found
            return found

        from openshell._proto import openshell_pb2

        spec = openshell_pb2.SandboxSpec()
        if self._custom_image:
            spec.template.image = self._custom_image

        assert self._gateway is not None
        ref = self._gateway.create(
            spec=spec,
            name=self._sandbox_name,
            labels=self._sandbox_labels,
        )

        ref = self._client.wait_ready(ref.name, timeout_seconds=60.0)
        self._active_sandbox = ref
        return ref

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)

        try:
            sandbox = self._get_or_create_sandbox()
            result = self._client.exec(
                sandbox.id,
                ["bash", "-c", inp.cmd],
                workdir=inp.workdir,
                env=inp.env,
                timeout_seconds=inp.timeout_seconds,
            )

            if result.exit_code == 0:
                return result.stdout.strip() if result.stdout.strip() else "(no output)"

            parts = [f"EXIT CODE: {result.exit_code}"]
            if result.stdout.strip():
                parts.append(result.stdout.strip())
            if result.stderr.strip():
                parts.append(f"STDERR:\n{result.stderr.strip()}")
            return "\n".join(parts)

        except RuntimeError:
            raise
        except Exception as exc:
            self._active_sandbox = None
            return f"ERROR: Failed to execute command in sandbox: {exc}"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Delete sandbox (if keep_sandbox is False) and release resources."""
        if self._active_sandbox is not None and not self._keep_sandbox:
            if self._client is not None:
                try:
                    self._client.delete(self._active_sandbox.name)
                except Exception:
                    pass
            self._active_sandbox = None

        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._gateway = None

        if self._tmp_dir is not None:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
