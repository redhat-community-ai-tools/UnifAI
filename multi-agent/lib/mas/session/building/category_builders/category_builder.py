from abc import ABC, abstractmethod
from typing import Any, ClassVar, Iterable, Optional
from mas.elements.common.exceptions import PluginConfigurationError
from pydantic import ValidationError
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.enums import ResourceCategory
from mas.core.contracts import SessionRegistry
from mas.core.element_deps import ElementBuildContext
from mas.blueprints.models.blueprint import BlueprintSpec, ResourceSpec


class CategoryBuilder(ABC):
    """SRP: one concrete subclass per resource category."""

    # must be overridden
    category: ClassVar[ResourceCategory]
    depends_on: ClassVar[tuple[ResourceCategory, ...]] = ()

    def __init__(self, registry_elements) -> None:
        self._registry_elements = registry_elements

    def build(
        self,
        blueprint: BlueprintSpec,
        registry: SessionRegistry,
        deps: Optional[ElementBuildContext] = None,
    ) -> None:
        for resource in self._iter_specs(blueprint):
            spec = self._registry_elements.get_spec(self.category, resource.type)
            inst = self._create_instance(resource, registry, deps=deps)
            self._register(registry, resource.rid.ref, inst, spec, resource)

    # -------- protected helpers ----------------------------------------

    @abstractmethod
    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[ResourceSpec]:
        ...

    def _register(self, registry, name: str, inst: Any, spec: Any, resource_spec: Any):
        registry.register(self.category, name, inst, spec, resource_spec)

    def _resolve_auth_credential(
        self,
        cfg: Any,
        deps: Optional[ElementBuildContext],
    ) -> Any:
        """
        Bind a lazy OAuth credential when cfg names a registry auth server.

        Static dropdown values (none / access_token) must not bind.
        Returns the credential or None.
        """
        server_id = (getattr(cfg, "server_identifier", "") or "").rstrip("/")
        scheme_type = getattr(cfg, "scheme_type", "") or ""
        if (
            not server_id
            or server_id in StaticAuthMethod.values()
            or not deps
            or not deps.auth_service
        ):
            return None

        ctx_holder = getattr(deps, "execution_ctx", None)
        if not ctx_holder:
            return None

        def resolver(_h=ctx_holder) -> str:
            return _h.context.credential_user_id()

        return deps.auth_service.bind_lazy(resolver, server_id, scheme_type)

    # ––– shared factory construction with error handling ––––––––––––––
    def _create_instance(
        self,
        resource_spec: ResourceSpec,
        session_registry: SessionRegistry,
        deps: Optional[ElementBuildContext] = None,
    ) -> Any:
        """Lookup factory, validate schema, create instance with extras."""
        try:
            factory_cls = self._registry_elements.get_factory_class(self.category, resource_spec.type)
            schema_cls = self._registry_elements.get_schema(self.category, resource_spec.type)
        except KeyError as e:
            raise PluginConfigurationError(
                f"No plugin for {self.category!r} type={resource_spec.type!r}", resource_spec.config.dict()
            ) from e

        raw = resource_spec.config.dict(exclude_unset=True)
        try:
            validated = schema_cls(**raw) if schema_cls else raw
        except ValidationError as ve:
            raise PluginConfigurationError(
                f"Config validation failed for {self.category}/{resource_spec.type}: {ve}", raw
            ) from ve

        factory = factory_cls()
        if not factory.accepts(cfg=validated, element_type=resource_spec.type):
            raise PluginConfigurationError(
                f"{factory_cls.__name__} rejects config of element resource type `{resource_spec.type}`", validated
            )

        try:
            extra = self._extra_kwargs(resource_spec.config, session_registry, deps=deps)
            return factory.create(validated, deps=deps, **extra)
        except Exception as e:
            raise PluginConfigurationError(
                f"{factory_cls.__name__}.create() failed: {e}", validated
            ) from e

    # subclasses may override
    def _extra_kwargs(
        self, cfg, session_registry: SessionRegistry, deps: Optional[ElementBuildContext] = None,
    ) -> dict[str, Any]:
        return {}
