"""Sandbox Exec Tool — execute shell commands in OpenShell sandbox containers.

Follows the same ``{cmd: str}`` pattern as ``SshExecTool``.  The tool
handles sandbox lifecycle internally: lazy creation on first use,
reconnection via server-side label filtering, and cleanup on close.

Communicates with the OpenShell gateway via raw gRPC using bundled
protobuf stubs (``_proto/``).  The ``grpcio`` dependency is imported
lazily so the tool can be registered without it installed.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)

_RPC_TIMEOUT = 300.0
_READY_POLL_INTERVAL = 2.0
_READY_TIMEOUT = 60.0


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


@dataclass
class SandboxRef:
    """Lightweight handle to a sandbox returned by the gateway."""

    id: str
    name: str
    phase: int = 0


@dataclass
class ExecResult:
    """Collected output from a streamed ``ExecSandbox`` RPC."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


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
        self._channel: Any = None
        self._stub: Any = None
        self._active_sandbox: Optional[SandboxRef] = None

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
    # gRPC client lifecycle
    # ------------------------------------------------------------------

    def _ensure_client(self) -> None:
        """Lazily create a gRPC channel and ``OpenShellStub``."""
        if self._stub is not None:
            return

        try:
            import grpc
        except ImportError as exc:
            raise RuntimeError(
                "The 'grpcio' package is required for SandboxExecTool. "
                "Install it with: pip install 'grpcio>=1.60'"
            ) from exc

        from mas.elements.tools.sandbox_exec._proto import (
            openshell_pb2_grpc,
        )

        credentials = grpc.ssl_channel_credentials(
            root_certificates=self._ca_cert.encode(),
            private_key=self._tls_key.encode(),
            certificate_chain=self._tls_cert.encode(),
        )
        parsed = urlparse(self._gateway_url)
        endpoint = f"{parsed.hostname}:{parsed.port or 443}"

        self._channel = grpc.secure_channel(endpoint, credentials)
        self._stub = openshell_pb2_grpc.OpenShellStub(self._channel)

    # ------------------------------------------------------------------
    # Protobuf helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sandbox_from_pb(sandbox: Any) -> SandboxRef:
        """Extract a ``SandboxRef`` from a protobuf ``Sandbox`` message."""
        meta = sandbox.metadata
        status = sandbox.status if sandbox.HasField("status") else None
        return SandboxRef(
            id=meta.id if meta else "",
            name=meta.name if meta else "",
            phase=status.phase if status else 0,
        )

    # ------------------------------------------------------------------
    # Sandbox lifecycle (hidden from LLM)
    # ------------------------------------------------------------------

    def _find_my_sandbox(self) -> Optional[SandboxRef]:
        """Find the sandbox for this agent session via server-side label filter."""
        from mas.elements.tools.sandbox_exec._proto import openshell_pb2

        assert self._stub is not None
        response = self._stub.ListSandboxes(
            openshell_pb2.ListSandboxesRequest(
                label_selector=self._label_selector,
            ),
            timeout=_RPC_TIMEOUT,
        )
        for sb in response.sandboxes:
            ref = self._sandbox_from_pb(sb)
            if ref.phase == 2:  # SANDBOX_PHASE_READY
                return ref
        return None

    def _wait_ready(self, name: str, timeout: float = _READY_TIMEOUT) -> SandboxRef:
        """Poll ``GetSandbox`` until the sandbox reaches READY phase."""
        from mas.elements.tools.sandbox_exec._proto import openshell_pb2

        assert self._stub is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = self._stub.GetSandbox(
                openshell_pb2.GetSandboxRequest(name=name),
                timeout=10.0,
            )
            ref = self._sandbox_from_pb(resp.sandbox)
            if ref.phase == 2:  # SANDBOX_PHASE_READY
                return ref
            time.sleep(_READY_POLL_INTERVAL)
        raise TimeoutError(f"Sandbox {name!r} not ready within {timeout}s")

    def _get_or_create_sandbox(self) -> SandboxRef:
        """Return the cached sandbox, reconnect by labels, or create a new one."""
        if self._active_sandbox is not None:
            return self._active_sandbox

        self._ensure_client()

        found = self._find_my_sandbox()
        if found is not None:
            self._active_sandbox = found
            return found

        from mas.elements.tools.sandbox_exec._proto import openshell_pb2

        spec = openshell_pb2.SandboxSpec()
        if self._custom_image:
            spec.template.image = self._custom_image

        assert self._stub is not None
        response = self._stub.CreateSandbox(
            openshell_pb2.CreateSandboxRequest(
                spec=spec,
                name=self._sandbox_name,
                labels=self._sandbox_labels,
            ),
            timeout=_RPC_TIMEOUT,
        )
        created = self._sandbox_from_pb(response.sandbox)
        ref = self._wait_ready(created.name)
        self._active_sandbox = ref
        return ref

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _exec_in_sandbox(
        self,
        sandbox_id: str,
        command: List[str],
        *,
        workdir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> ExecResult:
        """Run a command via the streaming ``ExecSandbox`` RPC."""
        from mas.elements.tools.sandbox_exec._proto import openshell_pb2

        assert self._stub is not None
        request = openshell_pb2.ExecSandboxRequest(
            sandbox_id=sandbox_id,
            command=command,
            workdir=workdir or "",
            environment=env or {},
            timeout_seconds=timeout_seconds or 0,
        )

        stdout_parts: List[str] = []
        stderr_parts: List[str] = []
        exit_code = 0

        for event in self._stub.ExecSandbox(request, timeout=_RPC_TIMEOUT):
            if event.HasField("stdout"):
                stdout_parts.append(
                    event.stdout.data.decode("utf-8", errors="replace")
                )
            if event.HasField("stderr"):
                stderr_parts.append(
                    event.stderr.data.decode("utf-8", errors="replace")
                )
            if event.HasField("exit"):
                exit_code = event.exit.exit_code

        return ExecResult(
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            exit_code=exit_code,
        )

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)

        try:
            sandbox = self._get_or_create_sandbox()
            result = self._exec_in_sandbox(
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
            if self._stub is not None:
                try:
                    from mas.elements.tools.sandbox_exec._proto import (
                        openshell_pb2,
                    )

                    self._stub.DeleteSandbox(
                        openshell_pb2.DeleteSandboxRequest(
                            name=self._active_sandbox.name,
                        ),
                        timeout=30.0,
                    )
                except Exception:
                    pass
            self._active_sandbox = None

        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
            self._stub = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
