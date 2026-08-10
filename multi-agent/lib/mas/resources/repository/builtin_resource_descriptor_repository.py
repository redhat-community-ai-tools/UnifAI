from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from mas.core.enums import ResourceOwnership
from mas.core.identity import Identity
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.models import Resource


class BuiltinResourceDescriptorRepository(ABC):
    """Storage port for ``BuiltinResourceDescriptor`` documents — the sole
    owner of built-in ownership/visibility/parent_builtin_id metadata.

    Also exposes joined reads (``find_all_builtins``,
    ``find_visible_for_identity``) that combine descriptor metadata with
    the base ``resources`` collection, since the base ``Resource`` model
    itself carries no built-in-related fields to filter/sort on.
    """

    @abstractmethod
    def get(self, rid: str) -> Optional[BuiltinResourceDescriptor]:
        """Return the descriptor for *rid*, or ``None`` if *rid* is not a built-in."""
        ...

    @abstractmethod
    def save(self, descriptor: BuiltinResourceDescriptor) -> str:
        """Insert or update a descriptor (upsert on ``rid``)."""
        ...

    @abstractmethod
    def delete(self, rid: str) -> None:
        """Delete the descriptor for *rid*, if any."""
        ...

    @abstractmethod
    def find_all_rids(self) -> List[str]:
        """Return the rids of every built-in resource."""
        ...

    @abstractmethod
    def find_all_builtins(
        self,
        category: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> List[Resource]:
        """Return every built-in resource (public and draft), joined with
        the base ``resources`` collection, for admin listing.

        Unlike ``find_visible_for_identity``, this is unconditional — no
        identity scoping, no visibility gating, no pagination. Callers
        that need those (e.g. an authenticated but non-admin listing
        endpoint) should use ``find_visible_for_identity`` instead.
        """
        ...

    @abstractmethod
    def find_visible_for_identity(
        self,
        *,
        identity: Optional[Identity],
        category: Optional[str],
        resource_type: Optional[str],
        ownership: Optional[ResourceOwnership],
        is_admin: bool,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
    ) -> Tuple[List[Resource], int]:
        """Paginated resources visible to *identity*, joined with built-in
        descriptor metadata. Backs the generic ``/resources.list`` listing:

        - ``ownership=None``: *identity*'s own resources (any ownership
          state) plus public built-ins owned by anyone else.
        - ``ownership=CUSTOM``: *identity*'s own non-built-in resources only.
        - ``ownership=BUILTIN``: every built-in matching category/type,
          gated by *is_admin* for draft visibility (not scoped to *identity*).
        """
        ...
