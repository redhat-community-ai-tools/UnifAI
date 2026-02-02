"""OpenShift CLI execution tool."""

import re
import shlex
from contextlib import contextmanager
from typing import Any, Generator
from urllib.parse import urlparse

import openshift_client as oc
from pydantic import BaseModel, Field

from elements.tools.common.base_tool import BaseTool


class OcCommandInput(BaseModel):
    """Input schema for oc commands."""
    cmd: str = Field(..., description="The oc command to execute (without 'oc' prefix)")


class OcExecTool(BaseTool):
    """Execute OpenShift CLI commands on a cluster."""
    
    name: str = "oc_exec"
    description: str = "Execute oc commands on an OpenShift cluster"
    args_schema = OcCommandInput

    def __init__(self, *, server: str, token: str, skip_tls_verify: bool = False):
        super().__init__()
        self._server = server
        self._token = token
        self._skip_tls_verify = skip_tls_verify
        
        self.name = self._build_tool_name(server)
        self.description = self._build_description(server)
        
        self._validate_connection()

    @staticmethod
    def _build_tool_name(server: str) -> str:
        """Generate a unique tool name from the server URL."""
        parsed = urlparse(server)
        host = parsed.netloc or parsed.path
        sanitized = re.sub(r'[^a-zA-Z0-9]', '_', host)
        return f"oc_exec_{sanitized}"

    @staticmethod
    def _build_description(server: str) -> str:
        """Generate tool description."""
        return (
            f"Execute OpenShift 'oc' commands on cluster at {server}. "
            f"Provide the command without 'oc' prefix. "
            f"Examples: 'get pods', 'get deployments', 'describe pod <name>', 'logs <pod>'"
        )

    @contextmanager
    def _oc_context(self) -> Generator[None, None, None]:
        """Context manager for OpenShift client configuration."""
        with oc.api_server(self._server):
            with oc.token(self._token):
                with oc.tls_verify(enable=not self._skip_tls_verify):
                    yield

    def _validate_connection(self) -> None:
        """Validate connection to cluster on initialization."""
        with self._oc_context():
            oc.invoke('whoami')

    def _execute(self, command: str) -> str:
        """Execute an oc command and return the output."""
        parts = shlex.split(command)
        if not parts:
            return "Error: empty command"
        
        verb, args = parts[0], parts[1:]
        
        with self._oc_context():
            result = oc.invoke(verb, args)
        
        status = result.status()
        stdout = (result.out() or "").strip()
        stderr = (result.err() or "").strip()
        
        if stdout and stderr:
            return f"{stdout}\nstderr: {stderr}"
        if stdout or stderr:
            return stdout or stderr
        return f"(no output, exit code: {status})"

    def run(self, *args: Any, **kwargs: Any) -> str:
        """Execute the oc command."""
        try:
            command = self.args_schema(**kwargs).cmd
            return self._execute(command)
        except oc.OpenShiftPythonException as e:
            return str(e)
        except Exception as e:
            return f"Error: {e}"
