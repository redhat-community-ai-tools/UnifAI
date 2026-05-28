from typing import Any, Iterable, Optional

from .category_builder import CategoryBuilder, BlueprintSpec, ResourceSpec
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry
from mas.core.element_deps import ElementDeps
from mas.elements.common.exceptions import PluginConfigurationError


class ToolBuilder(CategoryBuilder):
    category = ResourceCategory.TOOL

    def _iter_specs(self, bp: BlueprintSpec) -> Iterable[ResourceSpec]:
        """Return tools sorted so ToolRef dependencies are built after their targets."""
        no_deps: list[ResourceSpec] = []
        has_deps: list[ResourceSpec] = []
        for resource in bp.tools:
            if self._has_tool_ref(resource.config):
                has_deps.append(resource)
            else:
                no_deps.append(resource)
        return no_deps + has_deps

    @staticmethod
    def _has_tool_ref(config: Any) -> bool:
        """Check if a tool config contains any ToolRef field."""
        from mas.core.ref.models import ToolRef
        for field_name in config.model_fields:
            if isinstance(getattr(config, field_name, None), ToolRef):
                return True
        return False

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
