from typing import Any, Iterable, Optional

from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry
from mas.core.element_deps import ElementDeps


class ProviderBuilder(CategoryBuilder):
    category = ResourceCategory.PROVIDER

    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[Any]:
        return blueprint.providers

    def _extra_kwargs(
        self, cfg: Any, session_registry: SessionRegistry, deps: Optional[ElementDeps] = None,
    ) -> dict[str, Any]:
        server_id = getattr(cfg, "server_identifier", "")
        scheme_type = getattr(cfg, "scheme_type", "")
        if server_id and deps and deps.auth_service:
            ctx_holder = getattr(deps, "execution_ctx", None)
            if ctx_holder:
                resolver = lambda _h=ctx_holder: _h.context.credential_user_id()
                cred = deps.auth_service.bind_lazy(resolver, server_id, scheme_type)
                if cred:
                    return {"auth_credential": cred}

        return {}
