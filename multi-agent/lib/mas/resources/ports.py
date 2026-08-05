"""
Ports (interfaces) for external dependencies of the resources domain.

Services and adapters depend on these ABCs rather than concrete
implementations, keeping the dependency arrows pointing inward.
"""
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
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
