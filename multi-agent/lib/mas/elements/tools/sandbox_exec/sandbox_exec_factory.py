from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import SandboxExecToolConfig
from .sandbox_exec import SandboxExecTool
from .identifiers import Identifier


class SandboxExecToolFactory(BaseFactory[SandboxExecToolConfig, SandboxExecTool]):
    """Factory for creating SandboxExecTool instances from config.

    Note: ``create()`` makes network calls indirectly via the tool
    constructor which builds a gRPC channel. This is consistent
    with SshExecToolFactory.
    """

    def accepts(self, cfg: SandboxExecToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: SandboxExecToolConfig, **kwargs: Any) -> SandboxExecTool:
        """Instantiate a SandboxExecTool from validated config.

        Args:
            cfg: Fully-validated SandboxExecToolConfig.

        Raises:
            PluginConfigurationError: If instantiation fails.
        """
        try:
            return SandboxExecTool(
                endpoint=cfg.gateway_url,
                ca_pem=cfg.ca_cert,
                cert_pem=cfg.tls_cert,
                key_pem=cfg.tls_key,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"SandboxExecToolFactory.create() failed: {e}",
                cfg.dict(),
            ) from e
