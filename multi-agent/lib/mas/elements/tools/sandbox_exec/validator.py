"""Validator for Sandbox Exec Tool."""

from __future__ import annotations

import shlex
from typing import List, TYPE_CHECKING
from socket import timeout as SocketTimeout, gaierror

from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.tools.sandbox_exec.config import SandboxExecToolConfig

if TYPE_CHECKING:
    import paramiko


class SandboxExecToolValidator(BaseElementValidator):
    """Validates VM has podman (and optionally git) via the referenced ssh_exec."""

    def validate(
        self,
        config: SandboxExecToolConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []
        checked_dependencies = {}

        ssh_rid = config.ssh_tool_ref.ref

        if not self._check_dependency(
            context, ssh_rid, "ssh_tool_ref", messages, checked_dependencies,
        ):
            return self._build_report(
                messages=messages,
                checked_dependencies=checked_dependencies,
            )

        ssh_cfg = context.dependency_configs.get(ssh_rid, {})
        if not ssh_cfg:
            messages.append(self._error(
                "DEPENDENCY_CONFIG_MISSING",
                f"Cannot read config for ssh_exec dependency '{ssh_rid}'",
                field="ssh_tool_ref",
            ))
            return self._build_report(
                messages=messages,
                checked_dependencies=checked_dependencies,
            )

        try:
            import paramiko as _paramiko
        except ImportError:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                "paramiko is not installed; cannot validate SSH",
                field="ssh_tool_ref",
            ))
            return self._build_report(
                messages=messages,
                checked_dependencies=checked_dependencies,
            )

        ssh_client = None
        try:
            ssh_client = _paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(_paramiko.AutoAddPolicy())
            ssh_client.connect(
                hostname=ssh_cfg["host"],
                port=ssh_cfg.get("port", 22),
                username=ssh_cfg["username"],
                password=ssh_cfg["password"],
                look_for_keys=False,
                allow_agent=False,
                timeout=context.timeout_seconds,
            )

            self._check_podman(ssh_client, messages)
            self._check_workspace_or_repo(ssh_client, config, messages)

        except _paramiko.AuthenticationException:
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                f"SSH authentication failed for user '{ssh_cfg.get('username')}'",
                field="ssh_tool_ref",
            ))
        except _paramiko.SSHException as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"SSH error: {e}",
                field="ssh_tool_ref",
            ))
        except SocketTimeout:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="ssh_tool_ref",
            ))
        except gaierror as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Cannot resolve hostname '{ssh_cfg.get('host')}': {e}",
                field="ssh_tool_ref",
            ))
        except ConnectionRefusedError:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection refused at {ssh_cfg.get('host')}:{ssh_cfg.get('port', 22)}",
                field="ssh_tool_ref",
            ))
        except OSError as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Network error: {e}",
                field="ssh_tool_ref",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Unexpected error: {type(e).__name__}: {e}",
                field="ssh_tool_ref",
            ))
        finally:
            if ssh_client is not None:
                try:
                    ssh_client.close()
                except Exception:
                    pass

        return self._build_report(
            messages=messages,
            checked_dependencies=checked_dependencies,
        )

    def _check_podman(
        self,
        ssh_client: "paramiko.SSHClient",
        messages: List[ValidationMessage],
    ) -> None:
        """Verify podman is available on the VM."""
        _, stdout, _ = ssh_client.exec_command("which podman")
        out = stdout.read().decode().strip()
        if out:
            messages.append(self._info(
                "PODMAN_OK",
                f"Podman found at {out}",
                field="ssh_tool_ref",
            ))
        else:
            messages.append(self._error(
                "PODMAN_NOT_FOUND",
                "podman binary not found on the VM",
                field="ssh_tool_ref",
            ))

    def _check_workspace_or_repo(
        self,
        ssh_client: "paramiko.SSHClient",
        config: SandboxExecToolConfig,
        messages: List[ValidationMessage],
    ) -> None:
        """Check git + clone, or just verify workspace writability."""
        ws = shlex.quote(config.workspace_path)

        if config.git_repo_url:
            self._check_git_repo(ssh_client, config, ws, messages)
        else:
            cmd = f"mkdir -p {ws} && test -w {ws} && echo OK"
            _, stdout, stderr = ssh_client.exec_command(cmd)
            out = stdout.read().decode().strip()
            if out == "OK":
                messages.append(self._info(
                    "WORKSPACE_OK",
                    f"Workspace '{config.workspace_path}' is writable",
                    field="workspace_path",
                ))
            else:
                err = stderr.read().decode().strip()
                messages.append(self._error(
                    "WORKSPACE_NOT_WRITABLE",
                    f"Workspace '{config.workspace_path}' is not writable"
                    + (f": {err}" if err else ""),
                    field="workspace_path",
                ))

    def _check_git_repo(
        self,
        ssh_client: "paramiko.SSHClient",
        config: SandboxExecToolConfig,
        ws: str,
        messages: List[ValidationMessage],
    ) -> None:
        """Verify git is available and clone/fetch the bare repo."""
        _, stdout, _ = ssh_client.exec_command("which git")
        out = stdout.read().decode().strip()
        if not out:
            messages.append(self._error(
                "GIT_NOT_FOUND",
                "git binary not found on the VM",
                field="ssh_tool_ref",
            ))
            return

        messages.append(self._info(
            "GIT_OK", f"Git found at {out}", field="ssh_tool_ref",
        ))

        url = config.git_repo_url
        if config.git_token:
            url = url.replace("://", f"://oauth2:{config.git_token}@")

        cmd = (
            f"mkdir -p {ws} && cd {ws} && "
            f"if [ -d repo.git ]; then "
            f"cd repo.git && git fetch --all 2>&1; "
            f"else git clone --bare {shlex.quote(url)} repo.git 2>&1; fi"
        )
        _, stdout, stderr = ssh_client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        clone_out = stdout.read().decode().strip()
        clone_err = stderr.read().decode().strip()

        if config.git_token:
            clone_out = clone_out.replace(config.git_token, "***")
            clone_err = clone_err.replace(config.git_token, "***")

        if exit_code == 0:
            messages.append(self._info(
                "GIT_REPO_OK",
                f"Repository cloned/fetched to {config.workspace_path}/repo.git",
                field="git_repo_url",
            ))
        else:
            detail = clone_err or clone_out
            messages.append(self._error(
                "GIT_REPO_FAILED",
                f"Failed to clone/fetch repository: {detail}",
                field="git_repo_url",
            ))
