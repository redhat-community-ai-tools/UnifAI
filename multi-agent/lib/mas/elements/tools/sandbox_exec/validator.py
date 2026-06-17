"""Validator for OpenShell Sandbox Exec Tool.

Performs a gRPC mTLS health check against the configured gateway to
verify connectivity and credentials before the tool is used.
"""
from typing import List
from urllib.parse import urlparse

from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.tools.sandbox_exec.config import SandboxExecToolConfig


class SandboxExecToolValidator(BaseElementValidator):
    """Validates mTLS connectivity to an OpenShell gateway via gRPC."""

    def validate(
        self,
        config: SandboxExecToolConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []

        try:
            import grpc
        except ImportError:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                "The 'grpcio' package is required for validation. "
                "Install it with: pip install 'grpcio>=1.60'",
                field="gateway_url",
            ))
            return self._build_report(messages=messages)

        channel = None
        try:
            parsed = urlparse(config.gateway_url)
            host = parsed.hostname or config.gateway_url
            port = parsed.port or 443
            target = f"{host}:{port}"

            credentials = grpc.ssl_channel_credentials(
                root_certificates=config.ca_cert.encode(),
                private_key=config.tls_key.encode(),
                certificate_chain=config.tls_cert.encode(),
            )

            channel = grpc.secure_channel(target, credentials)

            try:
                grpc.channel_ready_future(channel).result(
                    timeout=context.timeout_seconds
                )
                messages.append(self._info(
                    "CONNECTION_OK",
                    f"Successfully connected to OpenShell gateway at {target}",
                    field="gateway_url",
                ))
            except grpc.FutureTimeoutError:
                messages.append(self._error(
                    ValidationCode.NETWORK_TIMEOUT.value,
                    f"Connection timed out after {context.timeout_seconds}s "
                    f"connecting to {target}",
                    field="gateway_url",
                ))

        except grpc.RpcError as e:
            code = e.code() if hasattr(e, "code") else None
            if code == grpc.StatusCode.UNAUTHENTICATED:
                messages.append(self._error(
                    ValidationCode.INVALID_CREDENTIALS.value,
                    f"mTLS authentication failed: {e.details() if hasattr(e, 'details') else e}",
                    field="ca_cert",
                ))
            elif code == grpc.StatusCode.UNAVAILABLE:
                messages.append(self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    f"Gateway unreachable: {e.details() if hasattr(e, 'details') else e}",
                    field="gateway_url",
                ))
            else:
                messages.append(self._error(
                    ValidationCode.NETWORK_ERROR.value,
                    f"gRPC error: {e}",
                    field="gateway_url",
                ))
        except ValueError as e:
            messages.append(self._error(
                ValidationCode.INVALID_CREDENTIALS.value,
                f"Invalid certificate or key format: {e}",
                field="ca_cert",
            ))
        except OSError as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Network error: {e}",
                field="gateway_url",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                f"Unexpected error: {type(e).__name__}: {e}",
                field="gateway_url",
            ))
        finally:
            if channel is not None:
                try:
                    channel.close()
                except Exception:
                    pass

        return self._build_report(messages=messages)
