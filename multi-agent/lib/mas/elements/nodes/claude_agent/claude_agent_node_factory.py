"""
Claude Agent Node Factory
"""

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import ClaudeAgentNodeConfig
from .claude_agent_node import ClaudeAgentNode
from .identifiers import Identifier


class ClaudeAgentNodeFactory(BaseFactory[ClaudeAgentNodeConfig, ClaudeAgentNode]):
    """
    Factory for creating Claude Agent Node instances.

    Dependencies injected:
    - retriever: Optional retriever instance (resolved from RetrieverRef)
    - providers: Optional list of McpProvider instances (resolved from ProviderRef)
    """

    def accepts(self, cfg: ClaudeAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: ClaudeAgentNodeConfig, **deps):
        try:
            element_deps = deps.pop("deps", None)
            execution_holder = element_deps.execution_ctx if element_deps else None
            platform = element_deps.platform_config if element_deps else None
            shared_storage = platform.shared_storage if platform else "/app/shared"

            return ClaudeAgentNode(
                # Auth (Vertex AI)
                vertex_project_id=cfg.vertex_project_id,
                vertex_region=cfg.vertex_region,
                # Model
                model=cfg.model,
                # Agent behavior
                system_prompt=cfg.system_prompt,
                max_turns=cfg.max_turns,
                permission_mode=cfg.permission_mode,
                allowed_tools=cfg.allowed_tools,
                disallowed_tools=cfg.disallowed_tools,
                # Skills
                skills_repos=cfg.skills_repos,
                cwd=cfg.cwd,
                # Advanced
                env_vars=cfg.env_vars,
                # Runtime context
                execution_holder=execution_holder,
                shared_storage=shared_storage,
                # Integration
                tools=deps.pop("tools"),
                mcp_providers=deps.pop("providers"),
                retriever=deps.pop("retriever"),
                sandbox=deps.pop("sandbox", None),
                retries=cfg.retries,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"ClaudeAgentNodeFactory.create failed: {e}",
                cfg.dict(),
            ) from e
