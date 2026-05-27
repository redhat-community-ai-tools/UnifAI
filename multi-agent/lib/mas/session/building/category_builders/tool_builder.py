from typing import Any, Optional

from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry
from mas.core.element_deps import ElementDeps
from mas.elements.common.exceptions import PluginConfigurationError


class ToolBuilder(CategoryBuilder):
    category = ResourceCategory.TOOL

    def _iter_specs(self, bp: BlueprintSpec):
        return bp.tools

    def _extra_kwargs(
        self, cfg: Any, session_registry: SessionRegistry, deps: Optional[ElementDeps] = None,
    ) -> dict[str, Any]:
        """Resolve ToolRef dependencies for tools that reference other tools."""
        ssh_ref = getattr(cfg, "ssh_tool_ref", None)
        if ssh_ref and hasattr(ssh_ref, "ref"):
            try:
                ssh_tool = session_registry.get_instance(
                    category=ResourceCategory.TOOL, rid=ssh_ref.ref,
                )
                return {"ssh_exec_tool": ssh_tool}
            except KeyError:
                raise PluginConfigurationError(
                    f"sandbox_exec references ssh_exec '{ssh_ref.ref}' which is not "
                    f"registered in SessionRegistry. Ensure ssh_exec appears BEFORE "
                    f"sandbox_exec in the blueprint tools list.",
                    {},
                )
        return {}
