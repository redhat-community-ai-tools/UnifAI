"""OpenShell sandbox backend for the deepagents framework.

Bridges ``BaseSandbox`` to the existing ``SandboxExecTool`` gRPC session,
causing all 7 built-in file/shell tools (ls, read, write, edit, glob, grep,
execute) to route through the remote sandbox transparently.
"""

from __future__ import annotations

import base64
import logging
import shlex
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

if TYPE_CHECKING:
    from mas.elements.tools.sandbox_exec.sandbox_exec import SandboxExecTool

logger = logging.getLogger(__name__)


class OpenShellSandboxBackend(BaseSandbox):
    """Sandbox backend that delegates execution to an OpenShell sandbox via gRPC.

    All operations are routed through ``SandboxExecTool._get_or_create_session()``,
    which handles lazy creation, reconnection, and thread-safe access.
    """

    def __init__(self, sandbox_tool: SandboxExecTool) -> None:
        self._sandbox_tool = sandbox_tool

    @property
    def id(self) -> str:
        """Unique sandbox identifier."""
        return self._sandbox_tool._sandbox_name or "openshell-pending"

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """Execute a shell command inside the remote sandbox.

        The command is passed via stdin to bash rather than as a ``-c``
        argument because the OpenShell gateway rejects command arguments
        containing newline characters, and the deepagents framework
        generates multi-line Python scripts for file operations.

        Catches all exceptions and returns a graceful error response so that
        gRPC failures surface as command failures (exit_code=1) rather than
        crashing the agent.
        """
        try:
            session = self._sandbox_tool._get_or_create_session()
            result = session.exec(
                ["bash"],
                stdin=command.encode("utf-8"),
                timeout_seconds=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            return ExecuteResponse(output=output, exit_code=result.exit_code)
        except Exception as exc:
            logger.warning("Sandbox execution failed: %s", exc, exc_info=True)
            return ExecuteResponse(
                output=f"Sandbox execution error: {exc}", exit_code=1
            )

    def upload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        """Write files into the sandbox using stdin pipe.

        Uses ``session.exec(cmd, stdin=content)`` to transfer file content
        without base64 encoding overhead.
        """
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                session = self._sandbox_tool._get_or_create_session()
                parent = str(PurePosixPath(path).parent)
                cmd = f"mkdir -p {shlex.quote(parent)} && cat > {shlex.quote(path)}"
                result = session.exec(
                    ["bash", "-c", cmd],
                    stdin=content,
                )
                if result.exit_code != 0:
                    error_msg = result.stderr or result.stdout or "unknown error"
                    responses.append(FileUploadResponse(path=path, error=error_msg))
                else:
                    responses.append(FileUploadResponse(path=path))
            except Exception as exc:
                logger.warning("Upload failed for %s: %s", path, exc, exc_info=True)
                responses.append(FileUploadResponse(path=path, error=str(exc)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download files from the sandbox via base64 encoding.

        Base64 is required because ``ExecResult.stdout`` is ``str`` —
        raw binary content would be corrupted by string decoding.
        """
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                session = self._sandbox_tool._get_or_create_session()
                result = session.exec(
                    ["bash", "-c", f"base64 {shlex.quote(path)}"],
                )
                if result.exit_code != 0:
                    error_msg = result.stderr or result.stdout or "file_not_found"
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error=error_msg)
                    )
                else:
                    content = base64.b64decode(result.stdout.strip())
                    responses.append(
                        FileDownloadResponse(path=path, content=content)
                    )
            except Exception as exc:
                logger.warning(
                    "Download failed for %s: %s", path, exc, exc_info=True
                )
                responses.append(
                    FileDownloadResponse(path=path, content=None, error=str(exc))
                )
        return responses
