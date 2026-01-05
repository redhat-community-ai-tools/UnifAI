"""Validator for SSH Exec Tool."""
import paramiko
from typing import List
from socket import timeout as SocketTimeout, gaierror

from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.tools.ssh_exec.config import SshExecToolConfig


class SshExecToolValidator(BaseElementValidator):
    """Validates SSH connection by attempting to connect."""

    def validate(
        self,
        config: SshExecToolConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []

        ssh_client = None
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                hostname=config.host,
                port=config.port,
                username=config.username,
                password=config.password,
                look_for_keys=False,
                allow_agent=False,
                timeout=context.timeout_seconds,
            )

            # Verify transport is active
            transport = ssh_client.get_transport()
            if transport is not None and transport.is_active():
                messages.append(self._info(
                    "CONNECTION_OK",
                    f"Successfully connected to SSH server at {config.host}:{config.port}",
                    field="host",
                ))
            else:
                messages.append(self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    "SSH transport not active after connection",
                    field="host",
                ))

        except paramiko.AuthenticationException:
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                f"Authentication failed for user '{config.username}'",
                field="password",
            ))
        except paramiko.SSHException as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"SSH error: {str(e)}",
                field="host",
            ))
        except SocketTimeout:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="host",
            ))
        except gaierror as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Cannot resolve hostname '{config.host}': {str(e)}",
                field="host",
            ))
        except ConnectionRefusedError:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection refused at {config.host}:{config.port}",
                field="host",
            ))
        except OSError as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Network error: {str(e)}",
                field="host",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Unexpected error: {type(e).__name__}: {str(e)}",
                field="host",
            ))
        finally:
            if ssh_client is not None:
                try:
                    ssh_client.close()
                except Exception:
                    pass

        return self._build_report(messages=messages)

