"""Validator for Sandbox Exec Tool — PEM pre-check + gRPC health check."""

from typing import List

from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from .config import SandboxExecToolConfig


class SandboxExecToolValidator(BaseElementValidator):
    """Validates gateway connectivity via mTLS gRPC health check."""

    @staticmethod
    def _parse_endpoint(gateway_url: str) -> str:
        """Extract host:port from gateway URL.

        Accepts formats:
          - "host:port"         → "host:port"
          - "https://host:port" → "host:port"
          - "host"              → "host:443" (default gRPC TLS port)
        """
        url = gateway_url.strip()
        if "://" in url:
            url = url.split("://", 1)[1]
        url = url.rstrip("/")
        if ":" not in url:
            url = f"{url}:443"
        return url

    def validate(
        self,
        config: SandboxExecToolConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []

        for field in ("ca_cert", "tls_cert", "tls_key"):
            value = getattr(config, field, "")
            if not value or "-----BEGIN" not in value:
                return self._build_report(messages=[
                    self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        f"'{field}' is empty or not valid PEM",
                        field=field,
                    )
                ])

        try:
            endpoint = self._parse_endpoint(config.gateway_url)
        except Exception as e:
            return self._build_report(messages=[
                self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    f"Invalid gateway URL: {e}",
                    field="gateway_url",
                )
            ])

        try:
            import grpc
            from .client import create_client_from_pem

            client = create_client_from_pem(
                endpoint,
                ca_pem=config.ca_cert,
                cert_pem=config.tls_cert,
                key_pem=config.tls_key,
                timeout=context.timeout_seconds,
            )
            try:
                resp = client.health()
                messages.append(self._info(
                    "CONNECTION_OK",
                    f"Gateway v{resp.version}",
                    field="gateway_url",
                ))
            finally:
                client.close()

        except ImportError:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                "openshell package is not installed. Install with: pip install 'mas[openshell]'",
                field="gateway_url",
            ))
        except Exception as e:
            import grpc as _grpc
            if isinstance(e, _grpc.RpcError) and hasattr(e, "code"):
                code = e.code()
                if code == _grpc.StatusCode.UNAVAILABLE:
                    messages.append(self._error(
                        ValidationCode.ENDPOINT_UNREACHABLE.value,
                        f"Gateway unreachable at {endpoint}",
                        field="gateway_url",
                    ))
                elif code == _grpc.StatusCode.UNAUTHENTICATED:
                    messages.append(self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        "mTLS authentication failed — check certificates",
                        field="ca_cert",
                    ))
                elif code == _grpc.StatusCode.DEADLINE_EXCEEDED:
                    messages.append(self._error(
                        ValidationCode.NETWORK_TIMEOUT.value,
                        f"Connection timed out after {context.timeout_seconds}s",
                        field="gateway_url",
                    ))
                else:
                    messages.append(self._error(
                        ValidationCode.NETWORK_ERROR.value,
                        f"gRPC error: {code.name} — {e.details() if hasattr(e, 'details') else e}",
                        field="gateway_url",
                    ))
            else:
                messages.append(self._error(
                    ValidationCode.NETWORK_ERROR.value,
                    f"Unexpected error: {type(e).__name__}: {e}",
                    field="gateway_url",
                ))

        return self._build_report(messages=messages)
