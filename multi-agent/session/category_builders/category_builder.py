from abc import ABC, abstractmethod
from typing import Any, ClassVar, Iterable
from elements.common.exceptions import PluginConfigurationError
from pydantic import ValidationError
from core.enums import ResourceCategory
from core.contracts import SessionRegistry
from blueprints.models.blueprint import BlueprintSpec, ResourceSpec


class CategoryBuilder(ABC):
    """SRP: one concrete subclass per resource category."""

    # must be overridden
    category: ClassVar[ResourceCategory]
    depends_on: ClassVar[tuple[ResourceCategory, ...]] = ()

    def __init__(self, registry_elements) -> None:
        self._registry_elements = registry_elements

    def build(self, blueprint: BlueprintSpec, registry: SessionRegistry) -> None:
        for resource in self._iter_specs(blueprint):
            # Get spec once
            spec = self._registry_elements.get_spec(self.category, resource.type)
            
            # Create instance
            inst = self._create_instance(resource, registry)
            
            # Store complete runtime element (instance + spec + resource_spec)
            self._register(registry, resource.rid.ref, inst, spec, resource)

    # -------- protected helpers ----------------------------------------

    @abstractmethod
    def _iter_specs(self, blueprint: BlueprintSpec) -> Iterable[ResourceSpec]:
        ...

    def _register(self, registry, name: str, inst: Any, spec: Any, resource_spec: Any):
        registry.register(self.category, name, inst, spec, resource_spec)

    # ––– shared factory construction with error handling ––––––––––––––
    def _create_instance(self, resource_spec: ResourceSpec, session_registry: SessionRegistry) -> Any:
        """Lookup factory, validate schema, create instance with extras."""
        try:
            factory_cls = self._registry_elements.get_factory_class(self.category, resource_spec.type)
            schema_cls = self._registry_elements.get_schema(self.category, resource_spec.type)
        except KeyError as e:
            raise PluginConfigurationError(
                f"No plugin for {self.category!r} type={resource_spec.type!r}", resource_spec.config.dict()
            ) from e

        # schema validation / merge
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
            return factory.create(validated, **self._extra_kwargs(resource_spec.config, session_registry))
        except Exception as e:
            raise PluginConfigurationError(
                f"{factory_cls.__name__}.create() failed: {e}", validated
            ) from e

    # subclasses may override
    def _extra_kwargs(self, cfg, session_registry: SessionRegistry) -> dict[str, Any]:
        return {}
