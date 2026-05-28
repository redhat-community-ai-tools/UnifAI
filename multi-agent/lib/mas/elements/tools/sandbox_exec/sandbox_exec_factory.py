from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import SandboxExecToolConfig
from .sandbox_exec import SandboxExecTool
from .identifiers import Identifier


class SandboxExecToolFactory(
    BaseFactory[SandboxExecToolConfig, SandboxExecTool],
):
    """Factory for creating SandboxExecTool instances."""

    def accepts(self, cfg: SandboxExecToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: SandboxExecToolConfig, **kwargs: Any) -> SandboxExecTool:
        ssh_exec_tool = kwargs.get("ssh_exec_tool")
        if ssh_exec_tool is None:
            raise PluginConfigurationError(
                "SandboxExecToolFactory requires 'ssh_exec_tool' in kwargs. "
                "Ensure ssh_exec is listed BEFORE sandbox_exec in the "
                "blueprint tools list.",
                cfg.dict(),
            )

        try:
            return SandboxExecTool(
                ssh_exec_tool=ssh_exec_tool,
                workspace_path=cfg.workspace_path,
                git_repo_url=cfg.git_repo_url,
                git_token=cfg.git_token,
                container_image=cfg.container_image,
                output_limit=cfg.output_limit,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"SandboxExecToolFactory.create() failed: {e}",
                cfg.dict(),
            ) from e
