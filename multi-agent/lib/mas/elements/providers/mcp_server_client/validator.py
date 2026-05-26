"""
elements/providers/mcp_server_client/validator.py

Validator for MCP Provider — uses McpProviderFactory for a real connection probe.

Uses the same transport path as the wizard and runtime (McpProviderFactory),
and resolves auth credentials via ``core/auth`` before probing.
"""

import time
import logging
from concurrent.futures import CancelledError
from typing import List

import anyio
from global_utils.utils.async_bridge import get_async_bridge
from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.providers.mcp_server_client.config import (
    McpAuthMethod,
    McpProviderConfig,
)
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory

logger = logging.getLogger(__name__)


class McpProviderValidator(BaseElementValidator):
    """
    Validates MCP Provider configuration.

    Uses McpProviderFactory.create_async() for a real MCP connection probe,
    matching the same transport path the wizard and runtime use.
    """

    def __init__(self, factory: McpProviderFactory = None):
        super().__init__()
        self._factory = factory or McpProviderFactory()

    def validate(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []

        try:
            with get_async_bridge() as bridge:
                bridge.run(self._check_connection(config, context, messages))
        except (CancelledError, TimeoutError) as e:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                str(e),
                field="mcp_url",
            ))
        except Exception as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {e}",
                field="mcp_url",
            ))

        return self._build_report(messages=messages)

    async def _check_connection(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
        messages: List[ValidationMessage],
    ) -> None:
        lookup_id = getattr(config, "server_identifier", "") or str(config.mcp_url)
        scheme_type = getattr(config, "scheme_type", "") or ""

        auth_method = getattr(config, "auth_method", None)
        is_sign_in = auth_method == McpAuthMethod.SIGN_IN or getattr(
            auth_method, "value", None,
        ) == McpAuthMethod.SIGN_IN.value

        auth_cred = None
        if context.auth_service:
            # For SIGN_IN (OAuth), credentials are stored per human member, never on a team.
            # credential_lookup_user_id() handles the owner-vs-credential-user resolution.
            lookup_user = context.credential_lookup_user_id() if is_sign_in else (context.user_id or "").strip()
            if lookup_user:
                auth_cred = context.auth_service.bind(
                    lookup_user, lookup_id, scheme_type=scheme_type,
                )

        try:
            start = time.time()
            with anyio.fail_after(context.timeout_seconds):
                await self._factory.create_async(config, auth_credential=auth_cred)

            elapsed = (time.time() - start) * 1000
            messages.append(self._info(
                "CONNECTION_OK",
                f"Connected to MCP server at {config.mcp_url} ({elapsed:.0f}ms)",
                field="mcp_url",
            ))

        except TimeoutError:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="mcp_url",
            ))
        except RuntimeError:
            raise
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                messages.append(self._error(
                    ValidationCode.INVALID_CREDENTIALS.value,
                    "Server rejected the credentials — sign in again or update your access token",
                    field="mcp_url",
                ))
            elif "403" in error_msg or "Forbidden" in error_msg:
                messages.append(self._error(
                    ValidationCode.INVALID_CREDENTIALS.value,
                    "Authenticated but not authorized — check your scopes or contact the server administrator",
                    field="mcp_url",
                ))
            else:
                messages.append(self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    f"Connection failed: {e}",
                    field="mcp_url",
                ))
