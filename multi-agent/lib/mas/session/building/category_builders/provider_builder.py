from typing import Any, Iterable, Optional

from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry
from mas.core.element_deps import ElementBuildContext


class ProviderBuilder(CategoryBuilder):
    category = ResourceCategory.PROVIDER

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.providers

    def _extra_kwargs(
        self, cfg: Any, session_registry: SessionRegistry, deps: Optional[ElementBuildContext] = None,
    ) -> dict[str, Any]:
        cred = self._resolve_auth_credential(cfg, deps)
        return {"auth_credential": cred} if cred else {}
