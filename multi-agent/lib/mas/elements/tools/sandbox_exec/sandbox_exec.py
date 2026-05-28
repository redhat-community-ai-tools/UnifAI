"""Sandbox execution tool with per-agent isolation.

Provides each agent its own workspace (git worktree or plain directory)
and Podman container, all running on a shared VM via an ssh_exec tool.
All commands run inside the container — the agent uses standard shell
commands (ls, cat, python, pip) like a developer.
"""

from __future__ import annotations

import re
import shlex
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool


_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_\-]")
_EXIT_SENTINEL = "___SANDBOX_EXIT___"


class SandboxShellInput(BaseModel):
    """Input schema for the sandbox shell tool."""

    cmd: str = Field(..., description="Shell command to run in the sandbox container")


@dataclass
class AgentSandboxState:
    """Mutable per-agent state tracking workspace and container readiness."""

    workspace_path: str = ""
    container_name: str = ""
    workspace_ready: bool = False
    container_ready: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class SandboxExecTool(BaseTool):
    """Shared sandbox tool — produces per-agent proxies via SupportsAgentScoping.

    Registered once in SessionRegistry. Each agent node that references this tool
    receives an isolated ``_SandboxAgentProxy`` with its own workspace + container.
    Direct invocation returns an error message.
    """

    name: str = "sandbox_exec"
    description: str = ""
    args_schema = SandboxShellInput

    def __init__(
        self,
        *,
        ssh_exec_tool: BaseTool,
        workspace_path: str,
        git_repo_url: str,
        git_token: str,
        container_image: str = "python:3.11-slim",
        output_limit: int = 10000,
    ) -> None:
        super().__init__()
        self._ssh = ssh_exec_tool
        self._workspace_path = workspace_path
        self._git_repo_url = git_repo_url
        self._git_token = git_token
        self._container_image = container_image
        self._output_limit = output_limit
        self._agent_states: Dict[str, AgentSandboxState] = {}
        self._states_lock = threading.Lock()

        safe_host = _SANITIZE_RE.sub("_", getattr(ssh_exec_tool, "_host", "vm"))
        self.name = f"sandbox_exec_{safe_host}"
        self.description = (
            f"Run a shell command in an isolated sandbox container on the VM.\n\n"
            f"The sandbox provides:\n"
            f"- A Podman container ({container_image}) with /workspace mounted\n"
            f"- Your project files at /workspace (git clone or empty directory)\n"
            f"- Full shell access: ls, cat, python, pip, git, etc.\n\n"
            f"Examples:\n"
            f"- ls /workspace              # list files\n"
            f"- cat /workspace/main.py     # read a file\n"
            f"- python /workspace/main.py  # run code\n"
            f"- pip install pandas          # install packages\n\n"
            f"The working directory is /workspace."
        )

    def scoped_for_agent(self, agent_uid: str) -> BaseTool:
        """Return an isolated proxy for *agent_uid*.

        Idempotent: repeated calls with the same uid produce a new proxy
        backed by the same underlying ``AgentSandboxState``.
        """
        with self._states_lock:
            if agent_uid not in self._agent_states:
                self._agent_states[agent_uid] = AgentSandboxState()
        return _SandboxAgentProxy(parent=self, agent_uid=agent_uid)

    def run(self, *args: Any, **kwargs: Any) -> str:
        return (
            "ERROR: SandboxExecTool must be scoped to an agent. "
            "This is an internal error — the tool should have been "
            "replaced by a proxy via SupportsAgentScoping."
        )


class _SandboxAgentProxy(BaseTool):
    """Per-agent proxy — all commands run inside the agent's Podman container."""

    name: str = "sandbox_proxy"
    description: str = ""
    args_schema = SandboxShellInput

    def __init__(self, parent: SandboxExecTool, agent_uid: str) -> None:
        super().__init__()
        self._parent = parent
        self._uid = agent_uid
        self.name = parent.name
        self.description = parent.description

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)
        if not inp.cmd.strip():
            return "ERROR: 'cmd' is required"

        state = self._parent._agent_states[self._uid]
        self._ensure_workspace(state)
        self._ensure_container(state)

        try:
            output = self._run_in_container(state, inp.cmd)
            return self._truncate(output)
        except Exception as exc:
            return f"ERROR: {exc}"

    # ── SSH execution ──────────────────────────────────────────────────

    def _run_ssh(self, cmd: str) -> Tuple[int, str]:
        """Execute *cmd* via the shared ssh_exec tool and return (exit_code, output).

        Wraps the command to capture exit code reliably since SshExecTool
        swallows errors into return strings rather than raising exceptions.
        """
        wrapped = f"{{ {cmd} ; }} 2>&1; echo '{_EXIT_SENTINEL}:'$?"
        raw: str = self._parent._ssh.run(cmd=wrapped)

        lines = raw.rsplit("\n", 1)
        if len(lines) == 2 and lines[1].startswith(f"{_EXIT_SENTINEL}:"):
            try:
                exit_code = int(lines[1].split(":")[1])
            except (ValueError, IndexError):
                exit_code = 1
            output = lines[0]
        else:
            exit_code = 1 if raw.startswith(("ERROR:", "STDERR:")) else 0
            output = raw

        return exit_code, output

    # ── Workspace provisioning ─────────────────────────────────────────

    def _ensure_workspace(self, state: AgentSandboxState) -> None:
        """Create workspace for this agent on first call (double-checked locking)."""
        if state.workspace_ready:
            return
        with state.lock:
            if state.workspace_ready:
                return

            safe_uid = _SANITIZE_RE.sub("_", self._uid)
            ws = shlex.quote(self._parent._workspace_path)

            if self._parent._git_repo_url:
                wt_path = f"{self._parent._workspace_path}/wt-{safe_uid}"
                wt = shlex.quote(wt_path)
                cmd = (
                    f"cd {ws}/repo.git && "
                    f"git worktree add {wt} HEAD 2>/dev/null || true"
                )
            else:
                wt_path = f"{self._parent._workspace_path}/agent-{safe_uid}"
                wt = shlex.quote(wt_path)
                cmd = f"mkdir -p {wt}"

            self._run_ssh(cmd)
            state.workspace_path = wt_path
            state.container_name = f"sandbox-{safe_uid}"
            state.workspace_ready = True

    def _ensure_container(self, state: AgentSandboxState) -> None:
        """Ensure the agent's Podman container is running, reusing if it already exists.

        Checks the VM first — if a container with this name is already running,
        it is reused (preserving installed packages, env vars, processes).
        Only creates a new container if none exists.
        """
        if state.container_ready:
            return
        with state.lock:
            if state.container_ready:
                return
            name = shlex.quote(state.container_name)
            wt = shlex.quote(state.workspace_path)
            image = shlex.quote(self._parent._container_image)

            check_cmd = f"podman inspect --format '{{{{.State.Running}}}}' {name} 2>/dev/null"
            exit_code, running = self._run_ssh(check_cmd)
            if exit_code == 0 and "true" in running.strip().lower():
                state.container_ready = True
                return

            cmd = (
                f"podman run -d --replace --name {name} "
                f"--timeout 7200 --network slirp4netns "
                f"-v {wt}:/workspace:Z "
                f"{image} sleep infinity"
            )
            exit_code, output = self._run_ssh(cmd)
            if exit_code != 0:
                raise RuntimeError(f"Container provision failed: {output}")
            state.container_ready = True

    # ── Container execution ────────────────────────────────────────────

    def _run_in_container(self, state: AgentSandboxState, cmd: str) -> str:
        """Execute *cmd* inside the agent's Podman container."""
        name = shlex.quote(state.container_name)
        inner = f"cd /workspace && {cmd}"
        full_cmd = f"podman exec {name} bash -c {shlex.quote(inner)}"
        exit_code, output = self._run_ssh(full_cmd)

        if exit_code != 0 and "no such container" in output.lower():
            state.container_ready = False
            self._ensure_container(state)
            exit_code, output = self._run_ssh(full_cmd)

        if exit_code != 0 and output:
            return f"(exit code {exit_code})\n{output}"
        return output

    def _truncate(self, output: str) -> str:
        """Tail-truncate output if it exceeds the configured limit."""
        limit = self._parent._output_limit
        if len(output) <= limit:
            return output
        notice = f"\n\n(output truncated — {len(output)} chars total, showing last {limit})"
        return output[-(limit - len(notice)):] + notice
