"""
Ports (interfaces) for external dependencies of the resources domain.

Services and adapters depend on these ABCs rather than concrete
implementations, keeping the dependency arrows pointing inward.
"""
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from mas.collaboration.models import TeamEditLockHolder
from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.models import Resource


@runtime_checkable
class CredentialCleanupPort(Protocol):
    """Capability to delete stored credentials when no resource references them."""

    def delete_credential(self, user_id: str, server_identifier: str) -> None: ...


@runtime_checkable
class ResourceReader(Protocol):
    """Narrow read port: fetch a visibility-gated resource and resolve its config.

    This is all ``BlueprintResolver`` needs — it depends on this Protocol
    (satisfied structurally by ``ResourcesService``) rather than the full
    service, so its dependency graph doesn't implicitly grow every time
    ``ResourcesService`` gains an unrelated CRUD/validation/card concern.
    """

    def get_visible(self, rid: str, *, caller: CallerScope) -> Resource: ...

    def resolve_resource(self, resource: Resource, caller: CallerScope) -> BaseModel: ...


@runtime_checkable
class ResourceClonePort(Protocol):
    """Narrow port for cloning: raw fetch, create, name-conflict check, delete.

    This is all ``ShareCloner`` needs. Unlike ``BlueprintResolver`` it never
    calls ``get_visible``/``resolve_resource`` — it works with resources it
    already owns (or is authorized to clone) and builds config models itself
    via ``ElementRegistry``, so it gets its own narrow port rather than
    sharing ``ResourceReader``.
    """

    def get(self, rid: str) -> Resource: ...

    def save_resource(self, resource: Resource) -> Resource: ...

    def exists_by_name(
        self, identity: Identity, category: str, type_: str, name: str,
    ) -> bool: ...

    def delete(self, rid: str) -> None: ...


@runtime_checkable
class BuiltinDescriptorReader(Protocol):
    """Narrow read port for checking whether a resource is a built-in.

    ``ShareCloner`` needs only this single fact about a resource (never
    the full ``BuiltinResourceService`` admin/overlay/cascade surface) to
    decide whether to clone it or keep it shared by reference — satisfied
    structurally by ``BuiltinResourceService``.
    """

    def get_descriptor(self, rid: str) -> Optional[BuiltinResourceDescriptor]: ...


@runtime_checkable
class AdminEditLockReader(Protocol):
    """Narrow read port for checking whether a built-in resource is locked.

    ``ResourcesService.guard_write_access`` uses this to reject mutations
    when another admin holds the cooperative edit lock — satisfied
    structurally by ``AdminEditLockService``.
    """

    def get_admin_edit_lock(self, entity_id: str) -> Optional[TeamEditLockHolder]: ...
