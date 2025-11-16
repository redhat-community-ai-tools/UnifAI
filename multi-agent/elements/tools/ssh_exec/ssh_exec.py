import paramiko
from typing import Any
from pydantic import BaseModel, Field, SecretStr
from elements.tools.common.base_tool import BaseTool


class CommandInput(BaseModel):
    cmd: str = Field(..., description="Shell command to run on the VM")


class SshExecTool(BaseTool):
    """
    Synchronous + asynchronous execution over SSH.
    """
    name: str = "SshExecTool"
    description: str = "Execute a shell command on a remote VM via SSH"
    args_schema = CommandInput

    def __init__(self, *, host: str, port: int, username: str, password: str):
        super().__init__()
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        
        # Override name with unique identifier from config
        # Create translation table to replace special characters with underscores
        translation = str.maketrans('.:- /', '_____')
        safe_host = host.translate(translation)
        safe_username = username.translate(translation)
        self.name = f"ssh_exec_{safe_host}_{port}_{safe_username}"
        
        # Override description with config-specific details
        self.description = (
            f"Run shell commands on remote server at {host}:{port}.\n\n"
            f"This tool automatically connects to the server (as user '{username}') "
            f"and executes the command you provide. You only need to specify the command - "
            f"the tool handles the SSH connection, authentication, and execution.\n\n"
            f"Connection Details:\n"
            f"• Host: {host}\n"
            f"• Port: {port}\n"
            f"• User: {username}\n\n"
            f"Usage: Simply provide the shell command as an argument. "
            f"The tool will connect to this specific remote machine and run it."
        )

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)  # validate + parse
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                look_for_keys=False,
                allow_agent=False,
                timeout=30
            )
            stdin, stdout, stderr = ssh.exec_command(inp.cmd, timeout=30)
            out = stdout.read().decode()
            err = stderr.read().decode()
            return out.strip() if not err else f"STDERR:\n{err.strip()}"
        finally:
            ssh.close()
