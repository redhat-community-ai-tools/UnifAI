from typing import Any, Dict, Iterable, Optional, Union, get_origin, get_args
from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.element_deps import ElementBuildContext
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.elements.nodes.types import NodeSpec
from mas.elements.common.exceptions import PluginConfigurationError
from mas.core.ref.models import Ref
from mas.core.contracts import SessionRegistry

_STATIC_AUTH_IDS = {m.value for m in StaticAuthMethod}


class NodeBuilder(CategoryBuilder):
    """
    Injects resolved Ref dependencies into node constructors.
    
    Automatically discovers Ref-typed fields from the config schema
    and resolves them to instances. No manual mapping required.
    Also injects auth_credential for nodes with server_identifier
    (same pattern as ProviderBuilder).
    """
    category = ResourceCategory.NODE
    depends_on = {
        ResourceCategory.TOOL,
        ResourceCategory.LLM,
        ResourceCategory.RETRIEVER,
        ResourceCategory.PROVIDER,
        ResourceCategory.SANDBOX,
    }

    def _iter_specs(self, bp: BlueprintSpec) -> Iterable[NodeSpec]:
        return bp.nodes

    def _extra_kwargs(
        self, cfg: NodeSpec, reg: SessionRegistry, deps: Optional[ElementBuildContext] = None,
    ) -> Dict[str, Any]:
        """Resolve all Ref-typed fields and auth credentials."""
        kwargs: Dict[str, Any] = {
            name: self._resolve(getattr(cfg, name, None), cfg, reg)
            for name in self._get_ref_field_names(cfg)
        }

        server_id = (getattr(cfg, "server_identifier", "") or "").rstrip("/")
        scheme_type = getattr(cfg, "scheme_type", "")
        # Static dropdown values (none/access_token) are propagated into
        # server_identifier but must not bind OAuth credentials.
        if (
            server_id
            and server_id not in _STATIC_AUTH_IDS
            and deps
            and deps.auth_service
        ):
            ctx_holder = getattr(deps, "execution_ctx", None)
            if ctx_holder:
                def resolver(_h=ctx_holder) -> str:
                    return _h.context.credential_user_id()
                cred = deps.auth_service.bind_lazy(resolver, server_id, scheme_type)
                if cred:
                    kwargs["auth_credential"] = cred

        return kwargs

    def _get_ref_field_names(self, cfg: NodeSpec) -> Iterable[str]:
        """Yield field names that are typed as Ref (including Optional/List)."""
        for name, field_info in cfg.model_fields.items():
            if self._is_ref_type(field_info.annotation):
                yield name

    def _is_ref_type(self, annotation) -> bool:
        """Check if annotation is a Ref type."""
        if annotation is None:
            return False

        origin = get_origin(annotation)

        if origin is Union:
            return any(self._is_ref_type(a) for a in get_args(annotation) if a is not type(None))

        if origin is list:
            args = get_args(annotation)
            return bool(args) and self._is_ref_type(args[0])

        try:
            return isinstance(annotation, type) and issubclass(annotation, Ref)
        except TypeError:
            return False

    def _resolve(self, value: Any, cfg: NodeSpec, reg: SessionRegistry) -> Any:
        """Resolve Ref or list of Refs to instances."""
        if value is None:
            return None
        if isinstance(value, list):
            return [self._resolve_single(ref, cfg, reg) for ref in value]
        return self._resolve_single(value, cfg, reg)

    def _resolve_single(self, ref: Ref, cfg: NodeSpec, reg: SessionRegistry) -> Any:
        """Resolve a single Ref to its instance."""
        category = ref.get_category()
        try:
            return reg.get_instance(category=category, rid=ref.ref)
        except KeyError as e:
            node_label = getattr(cfg, 'name', cfg.type if hasattr(cfg, 'type') else 'unknown')
            raise PluginConfigurationError(
                f"Node '{node_label}': unknown {category.value} ref '{ref.ref}'",
                cfg.model_dump()
            ) from e
