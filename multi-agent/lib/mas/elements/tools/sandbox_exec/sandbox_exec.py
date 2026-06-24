"""OpenShell Sandbox Exec tool — execute commands in a remote sandbox.

Manages sandbox lifecycle via the OpenShell Python SDK:
create (with deterministic naming), reconnect, exec, exec_python, and
cleanup.  Supports ``keep_sandbox`` for session persistence and
``route_all_tools`` to enable MCP tool routing via ``SandboxToolProxy``.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
from uuid import uuid4

import grpc
from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)

_READY_PHASE = 2  # openshell_pb2.SANDBOX_PHASE_READY

_PYTHON_BINARIES = [
    "/usr/bin/python3.12",
    "/usr/bin/python3",
    "/sandbox/.venv/bin/python",
    "/sandbox/.venv/bin/python3",
]


class SandboxExecInput(BaseModel):
    """Args schema for the sandbox_exec tool."""

    cmd: str = Field(..., description="Shell command to execute in the sandbox")
    workdir: Optional[str] = Field(
        None, description="Working directory for the command (e.g. '/workspace')"
    )
    env: Optional[Dict[str, str]] = Field(
        None, description="Environment variables to inject for this command"
    )
    timeout_seconds: Optional[int] = Field(
        None, description="Command timeout in seconds (default: no limit)"
    )


class SandboxExecTool(BaseTool):
    """Execute shell commands inside an OpenShell sandbox via the gRPC SDK.

    The tool lazily creates a sandbox on first use, reconnects to an
    existing sandbox by deterministic name, and cleans up on close.
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
        keep_sandbox: bool = False,
    ) -> None:
        super().__init__()
        self._endpoint = endpoint
        self._ca_pem = ca_pem
        self._cert_pem = cert_pem
        self._key_pem = key_pem
        self._keep_sandbox = keep_sandbox

        self._client = self._build_client()
        self._session: Any = None
        self._sandbox_name: Optional[str] = None
        self._session_id: str = ""
        self._agent_id: str = ""
        self._session_lock = threading.Lock()
        self._allowed_endpoints: Set[Tuple[str, int]] = set()

        translation = str.maketrans(".:- /", "_____")
        safe_endpoint = endpoint.translate(translation)
        self.name = f"sandbox_exec_{safe_endpoint}"
        self.description = (
            f"Execute a shell command inside an OpenShell sandbox "
            f"on gateway {endpoint}."
        )

    def _build_client(self) -> Any:
        """Create a ``SandboxClient`` via the ephemeral-tempfile factory."""
        from .client import create_client_from_pem

        return create_client_from_pem(
            self._endpoint,
            ca_pem=self._ca_pem,
            cert_pem=self._cert_pem,
            key_pem=self._key_pem,
        )

    def bind_context(self, *, session_id: str = "", agent_id: str = "") -> None:
        """Late-bind execution context for deterministic sandbox naming."""
        self._session_id = session_id
        self._agent_id = agent_id

    def add_allowed_endpoints(self, urls: List[str]) -> None:
        """Register MCP/tool URLs that the sandbox needs to reach.

        Called by ``context_binder.get_sandbox_wrapped_mcp_tools()``
        before sandbox creation so the network policy includes these
        endpoints.
        """
        for url in urls:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if host:
                self._allowed_endpoints.add((host, port))

    def _build_sandbox_policy(self) -> Any:
        """Build a SandboxPolicy proto with network policies for allowed endpoints."""
        from openshell._proto import sandbox_pb2

        network_policies = {}
        for host, port in self._allowed_endpoints:
            safe_key = re.sub(r"[^a-z0-9]", "_", host.lower()).strip("_")[:50]
            policy_key = f"mcp_{safe_key}"

            endpoint_kwargs: Dict[str, Any] = {
                "host": host,
                "port": port,
                "protocol": "rest",
                "enforcement": "enforce",
                "access": "full",
            }
            if port == 443:
                endpoint_kwargs["tls"] = "terminate"

            network_policies[policy_key] = sandbox_pb2.NetworkPolicyRule(
                name=policy_key,
                endpoints=[sandbox_pb2.NetworkEndpoint(**endpoint_kwargs)],
                binaries=[
                    sandbox_pb2.NetworkBinary(path=p) for p in _PYTHON_BINARIES
                ],
            )

        if not network_policies:
            return None

        logger.info(
            "Built sandbox network policy with %d endpoints: %s",
            len(network_policies),
            list(network_policies.keys()),
        )

        return sandbox_pb2.SandboxPolicy(
            version=1,
            network_policies=network_policies,
        )

    @staticmethod
    def _sanitize(value: str) -> str:
        """Make a string DNS-label safe."""
        return re.sub(r"[^a-z0-9]", "-", value.lower()).strip("-")

    def _make_sandbox_name(self) -> str:
        """Generate a deterministic sandbox name from session + agent IDs."""
        if self._session_id and self._agent_id:
            safe_session = self._sanitize(self._session_id[:12])
            safe_agent = self._sanitize(self._agent_id[:12])
            return f"sb-{safe_session}-{safe_agent}"
        return f"sb-{uuid4().hex[:16]}"

    def _get_or_create_session(self) -> Any:
        """Return the cached SDK session, reconnect, or create a new sandbox.

        Thread-safe via double-checked locking for parallel tool calls.
        """
        if self._session is not None:
            return self._session

        with self._session_lock:
            if self._session is not None:
                return self._session

            from openshell import SandboxSession

            name = self._make_sandbox_name()

            try:
                ref = self._client.get(name)
                if ref.phase == _READY_PHASE:
                    self._session = SandboxSession(self._client, ref)
                    self._sandbox_name = name
                    logger.info("Reconnected to existing sandbox %s", name)
                    return self._session
            except grpc.RpcError as rpc_err:
                if hasattr(rpc_err, "code") and rpc_err.code() == grpc.StatusCode.NOT_FOUND:
                    logger.debug("Sandbox %s not found, creating new", name)
                else:
                    logger.warning("Unexpected gRPC error checking sandbox %s: %s", name, rpc_err)
            except Exception as exc:
                logger.warning("Error checking for sandbox %s: %s", name, exc)

            from openshell._proto import openshell_pb2

            spec_kwargs: Dict[str, Any] = {}
            policy = self._build_sandbox_policy()
            if policy is not None:
                spec_kwargs["policy"] = policy

            self._client._stub.CreateSandbox(
                openshell_pb2.CreateSandboxRequest(
                    name=name,
                    labels={
                        "unifai.session": self._session_id[:12],
                        "unifai.agent": self._agent_id[:12],
                    },
                    spec=openshell_pb2.SandboxSpec(**spec_kwargs),
                ),
                timeout=180.0,
            )

            ref = self._client.wait_ready(name)
            self._session = SandboxSession(self._client, ref)
            self._sandbox_name = name
            logger.info("Created sandbox %s", name)
            return self._session

    def run(self, *args: Any, **kwargs: Any) -> str:
        """Execute a shell command inside the sandbox."""
        inp = self.args_schema(**kwargs)
        session = self._get_or_create_session()
        result = session.exec(
            ["bash", "-c", inp.cmd],
            workdir=inp.workdir,
            env=inp.env,
            timeout_seconds=inp.timeout_seconds,
        )
        if result.exit_code == 0:
            return result.stdout.strip() or "(no output)"
        parts: List[str] = [f"EXIT CODE: {result.exit_code}"]
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"STDERR:\n{result.stderr.strip()}")
        return "\n".join(parts)

    def exec_python(
        self,
        function: Any,
        *,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        workdir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 300,
    ) -> Any:
        """Serialize a Python callable via cloudpickle and run it in the sandbox.

        The SDK handles cloudpickle serialization, bootstrap script, and
        env-var packing internally.  On failure the cached session is
        invalidated so the next call re-creates the sandbox.
        """
        session = self._get_or_create_session()
        try:
            return session.exec_python(
                function,
                args=args,
                kwargs=kwargs,
                workdir=workdir,
                env=env,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            logger.warning("exec_python failed, invalidating session: %s", exc)
            self._session = None
            self._sandbox_name = None
            raise

    def close(self) -> None:
        """Delete sandbox (unless keep_sandbox) and release the gRPC channel."""
        if self._sandbox_name and not self._keep_sandbox:
            try:
                self._client.delete(self._sandbox_name)
                logger.info("Deleted sandbox %s", self._sandbox_name)
            except Exception:
                logger.warning(
                    "Failed to delete sandbox %s", self._sandbox_name, exc_info=True
                )
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._session = None
        self._sandbox_name = None
        self._client = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
