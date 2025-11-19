import paramiko
from typing import Any, Optional
from pydantic import BaseModel, Field, SecretStr
from elements.tools.common.base_tool import BaseTool


class CommandInput(BaseModel):
    cmd: str = Field(..., description="Shell command to run on the VM")


class SshExecTool(BaseTool):
    """
    Synchronous + asynchronous execution over SSH with persistent connection.
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
        
        # Persistent SSH client
        self._ssh: Optional[paramiko.SSHClient] = None
        
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
        
        # Establish initial connection
        self._connect()

    def _connect(self) -> None:
        """Establish SSH connection."""
        if self._ssh is not None:
            try:
                self._ssh.close()
            except:
                pass
        
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            look_for_keys=False,
            allow_agent=False,
            timeout=30
        )

    def _is_connected(self) -> bool:
        """Check if SSH connection is alive."""
        if self._ssh is None:
            return False
        
        transport = self._ssh.get_transport()
        if transport is None or not transport.is_active():
            return False
        
        # Try a keepalive to verify connection
        try:
            transport.send_ignore()
            return True
        except:
            return False

    def _ensure_connected(self) -> None:
        """Ensure SSH connection is active, reconnect if needed."""
        if not self._is_connected():
            self._connect()

    def run(self, *args: Any, **kwargs: Any) -> str:
        inp = self.args_schema(**kwargs)  # validate + parse
        
        try:
            # Ensure we have an active connection
            self._ensure_connected()
            
            # Execute command on persistent connection
            stdin, stdout, stderr = self._ssh.exec_command(inp.cmd)
            out = stdout.read().decode()
            err = stderr.read().decode()
            return out.strip() if not err else f"STDERR:\n{err.strip()}"
        except Exception as e:
            # If command execution fails, try reconnecting once
            try:
                self._connect()
                stdin, stdout, stderr = self._ssh.exec_command(inp.cmd)
                out = stdout.read().decode()
                err = stderr.read().decode()
                return out.strip() if not err else f"STDERR:\n{err.strip()}"
            except Exception as retry_error:
                return f"ERROR: Failed to execute command even after reconnection: {str(retry_error)}"

    def close(self) -> None:
        """Explicitly close the SSH connection."""
        if self._ssh is not None:
            try:
                self._ssh.close()
            except:
                pass
            self._ssh = None

    def __del__(self):
        """Cleanup SSH connection when tool is garbage collected."""
        self.close()
