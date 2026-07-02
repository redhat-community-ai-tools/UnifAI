from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import OpenShellSandboxConfig
from .openshell_sandbox import OpenShellSandbox
from .identifiers import Identifier


class OpenShellSandboxFactory(BaseFactory[OpenShellSandboxConfig, OpenShellSandbox]):
    """Factory for creating OpenShellSandbox instances from config."""

    def accepts(self, cfg: OpenShellSandboxConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: OpenShellSandboxConfig, **kwargs: Any) -> OpenShellSandbox:
        try:
            return OpenShellSandbox(
                endpoint=cfg.gateway_url,
                ca_pem=cfg.ca_cert,
                cert_pem=cfg.tls_cert,
                key_pem=cfg.tls_key,
                keep_sandbox=cfg.keep_sandbox,
                workdir=cfg.workdir,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"OpenShellSandboxFactory.create() failed: {e}",
                cfg.model_dump(),
            ) from e
