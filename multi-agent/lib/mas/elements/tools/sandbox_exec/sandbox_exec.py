"""Sandbox execution tool with per-agent isolation.

Provides each agent its own workspace (git worktree or plain directory)
and Podman container, all running on a shared VM via an ssh_exec tool.
"""

from __future__ import annotations

import base64
import re
import shlex
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Tuple

from pydantic import BaseModel, Field

from mas.elements.tools.common.base_tool import BaseTool


_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_\-]")
_EXIT_SENTINEL = "___SANDBOX_EXIT___"


class SandboxExecInput(BaseModel):
    """Input schema for the multi-action sandbox tool."""

    action: Literal["exec", "write_file", "read_file", "list_files"] = Field(
        "exec",
        description=(
            "Action to perform: "
            "'list_files' lists workspace files (optional glob via 'path'). "
            "'read_file' reads a file (requires 'path'). "
            "'write_file' writes content to a file (requires 'path' and 'content'). "
            "'exec' runs a command in the container (requires 'cmd')."
        ),
    )
    cmd: str = Field("", description="Shell command to run (for action='exec')")
    path: str = Field(
        "", description="File path relative to /workspace (for read/write/list)"
    )
    content: str = Field("", description="File content (for action='write_file')")


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
    args_schema = SandboxExecInput

    def __init__(
        self,
        *,
        ssh_exec_tool: BaseTool,
        workspace_path: str,
        git_repo_url: str,
        git_token: str,
    ) -> None:
        super().__init__()
        self._ssh = ssh_exec_tool
        self._workspace_path = workspace_path
        self._git_repo_url = git_repo_url
        self._git_token = git_token
        self._agent_states: Dict[str, AgentSandboxState] = {}
        self._states_lock = threading.Lock()

        safe_host = _SANITIZE_RE.sub("_", getattr(ssh_exec_tool, "_host", "vm"))
        self.name = f"sandbox_exec_{safe_host}"
        self.description = (
            f"Interact with an isolated sandbox on the VM.\n\n"
            f"Actions:\n"
            f"- list_files: list workspace files (optional 'path' as glob pattern)\n"
            f"- read_file: read a file ('path' relative to /workspace)\n"
            f"- write_file: write a file ('path' + 'content')\n"
            f"- exec: run a shell command in the container ('cmd')\n\n"
            f"Start with list_files to explore, then read_file to inspect code."
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
    """Per-agent proxy — delegates SSH to parent, maintains own workspace + container."""

    name: str = "sandbox_proxy"
    description: str = ""
    args_schema = SandboxExecInput

    def __init__(self, parent: SandboxExecTool, agent_uid: str) -> None:
        super().__init__()
        self._parent = parent
        self._uid = agent_uid
        self.name = parent.name
        self.description = parent.description

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)

        if inp.action == "exec" and not inp.cmd:
            return "ERROR: 'cmd' is required for action='exec'"
        if inp.action == "write_file" and (not inp.path or not inp.content):
            return "ERROR: 'path' and 'content' are required for action='write_file'"
        if inp.action == "read_file" and not inp.path:
            return "ERROR: 'path' is required for action='read_file'"

        state = self._parent._agent_states[self._uid]
        self._ensure_workspace(state)

        try:
            if inp.action == "list_files":
                return self._list_files(state, inp.path)
            elif inp.action == "read_file":
                return self._read_file(state, inp.path)
            elif inp.action == "write_file":
                return self._write_file(state, inp.path, inp.content)
            elif inp.action == "exec":
                self._ensure_container(state)
                return self._exec(state, inp.cmd)
        except Exception as exc:
            return f"ERROR: {exc}"
        return "ERROR: unknown action"

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
        """Provision Podman container on first exec action."""
        if state.container_ready:
            return
        with state.lock:
            if state.container_ready:
                return
            name = shlex.quote(state.container_name)
            wt = shlex.quote(state.workspace_path)
            cmd = (
                f"podman run -d --replace --name {name} "
                f"--timeout 7200 --network slirp4netns "
                f"-v {wt}:/workspace:Z "
                f"python:3.11-slim sleep infinity"
            )
            exit_code, output = self._run_ssh(cmd)
            if exit_code != 0:
                raise RuntimeError(f"Container provision failed: {output}")
            state.container_ready = True

    # ── Action implementations ─────────────────────────────────────────

    def _list_files(self, state: AgentSandboxState, pattern: str) -> str:
        wt = shlex.quote(state.workspace_path)
        if pattern:
            cmd = f"find {wt} -name {shlex.quote(pattern)} -type f | sort"
        else:
            cmd = f"find {wt} -type f -not -path '*/.git/*' | sort"
        exit_code, output = self._run_ssh(cmd)
        if exit_code != 0:
            return f"ERROR: {output}"
        prefix = state.workspace_path.rstrip("/") + "/"
        lines = output.strip().splitlines()
        relative = [
            ln[len(prefix):] if ln.startswith(prefix) else ln for ln in lines
        ]
        return "\n".join(relative) if relative else "(no files found)"

    def _read_file(self, state: AgentSandboxState, path: str) -> str:
        full = f"{state.workspace_path}/{path}"
        cmd = f"cat {shlex.quote(full)}"
        exit_code, output = self._run_ssh(cmd)
        if exit_code != 0:
            return f"ERROR: {output}"
        return output

    def _write_file(
        self, state: AgentSandboxState, path: str, content: str,
    ) -> str:
        full = f"{state.workspace_path}/{path}"
        dir_path = "/".join(full.split("/")[:-1])
        encoded = base64.b64encode(content.encode()).decode()
        cmd = (
            f"mkdir -p {shlex.quote(dir_path)} && "
            f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(full)}"
        )
        exit_code, output = self._run_ssh(cmd)
        if exit_code != 0:
            return f"ERROR: {output}"
        return f"File written: {path}"

    def _exec(self, state: AgentSandboxState, cmd: str) -> str:
        name = shlex.quote(state.container_name)
        inner = f"cd /workspace && {cmd}"
        full_cmd = f"podman exec {name} bash -c {shlex.quote(inner)}"
        exit_code, output = self._run_ssh(full_cmd)

        if exit_code != 0 and "no such container" in output.lower():
            state.container_ready = False
            self._ensure_container(state)
            exit_code, output = self._run_ssh(full_cmd)

        return output
