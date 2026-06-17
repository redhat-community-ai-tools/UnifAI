from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import SandboxExecToolConfig
from .sandbox_exec import SandboxExecTool
from .identifiers import Identifier


class SandboxExecToolFactory(BaseFactory[SandboxExecToolConfig, SandboxExecTool]):
    """Factory for creating SandboxExecTool instances from config.

    No network calls happen at creation time — the factory only stores
    configuration.  The actual sandbox is created lazily on first use.
    """

    def accepts(self, cfg: SandboxExecToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: SandboxExecToolConfig, **kwargs: Any) -> SandboxExecTool:
        """Instantiate a SandboxExecTool from validated config."""
        try:
            return SandboxExecTool(
                gateway_url=cfg.gateway_url,
                ca_cert=cfg.ca_cert,
                tls_cert=cfg.tls_cert,
                tls_key=cfg.tls_key,
                custom_image=cfg.custom_image,
                keep_sandbox=cfg.keep_sandbox,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"SandboxExecToolFactory.create() failed: {e}",
                cfg.model_dump(),
            ) from e
