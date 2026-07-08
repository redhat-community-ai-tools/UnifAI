"""Validator for OpenShell Sandbox — PEM pre-check + gRPC health check."""

import importlib.metadata
import re
from typing import List, Optional, Tuple

from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from .config import OpenShellSandboxConfig
from .client import normalize_endpoint


def _get_installed_sdk_version() -> Optional[str]:
    """Return the installed openshell SDK version, or None if unavailable."""
    try:
        return importlib.metadata.version("openshell")
    except importlib.metadata.PackageNotFoundError:
        return None


def _parse_version_tuple(raw: str) -> Optional[Tuple[int, ...]]:
    """Parse a dotted version string into a comparable integer tuple.

    Strips pre-release suffixes (e.g. ``rc1``, ``dev3``, ``a1``) from each
    segment before parsing so that versions like ``"0.0.62rc1"`` are
    comparable rather than silently rejected.

    Returns None if the string is empty or contains no numeric content.
    """
    try:
        parts = raw.strip().split(".")
        numeric_parts = [int(re.sub(r"[^0-9].*", "", p)) for p in parts]
        return tuple(numeric_parts)
    except (ValueError, AttributeError):
        return None


class OpenShellSandboxValidator(BaseElementValidator):
    """Validates gateway connectivity via mTLS gRPC health check."""

    def validate(
        self,
        config: OpenShellSandboxConfig,
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
            endpoint = normalize_endpoint(config.gateway_url)
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
                self._check_gateway_version(resp.version, messages)
            finally:
                client.close()

        except ImportError:
            messages.append(self._error(
                ValidationCode.NETWORK_ERROR.value,
                "openshell package is not installed. Install with: pip install 'mas[openshell]'",
                field="gateway_url",
            ))
        except Exception as e:
            if isinstance(e, grpc.RpcError) and hasattr(e, "code"):
                code = e.code()
                if code == grpc.StatusCode.UNAVAILABLE:
                    messages.append(self._error(
                        ValidationCode.ENDPOINT_UNREACHABLE.value,
                        f"Gateway unreachable at {endpoint}",
                        field="gateway_url",
                    ))
                elif code == grpc.StatusCode.UNAUTHENTICATED:
                    messages.append(self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        "mTLS authentication failed — check certificates",
                        field="ca_cert",
                    ))
                elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
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

    def _check_gateway_version(
        self,
        gateway_version_str: str,
        messages: List[ValidationMessage],
    ) -> None:
        """Compare the remote gateway version against the installed SDK version.

        Emits a warning when the gateway is older than the SDK — the sandbox
        will still be created, but functionality is not guaranteed if the SDK
        introduced breaking changes between the two versions.
        """
        sdk_version_str = _get_installed_sdk_version()
        if not sdk_version_str or not gateway_version_str:
            return

        gateway_ver = _parse_version_tuple(gateway_version_str)
        sdk_ver = _parse_version_tuple(sdk_version_str)

        if gateway_ver is None or sdk_ver is None:
            messages.append(self._warning(
                "VERSION_MISMATCH",
                f"Could not parse gateway version '{gateway_version_str}' "
                f"or SDK version '{sdk_version_str}' for compatibility check.",
                field="gateway_url",
            ))
            return

        if gateway_ver < sdk_ver:
            messages.append(self._warning(
                "VERSION_MISMATCH",
                f"Gateway v{gateway_version_str} is older than the installed "
                f"SDK v{sdk_version_str}. Proper functionality cannot be "
                f"guaranteed if the SDK introduced breaking changes.",
                field="gateway_url",
            ))
