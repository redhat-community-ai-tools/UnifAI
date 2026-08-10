from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any, Optional

from mas.resources.models import Resource, ResourceQuery
from mas.resources.repository.base import ResourceRepository
from mas.blueprints.repository.repository import BlueprintRepository
from mas.resources.errors import ResourceInUseError
from mas.core.identity import Identity
from mas.core.dto import GroupedCount


class ResourcesRegistry:
    """Low-level CRUD + business rules (no Pydantic parsing)."""

    def __init__(
            self,
            repo: ResourceRepository,
            bp_repo: BlueprintRepository,
            cipher: Optional[Any] = None,
    ):
        self._repo = repo
        self._bp_repo = bp_repo
        self._cipher = cipher

    # ---------- write ----------
    def create(self, doc: Resource) -> Resource:
        # uniqueness guard
        if self._repo.find_by_name(doc.identity, doc.category, doc.type, doc.name):
            raise ValueError(f"{doc.category}:{doc.type}:{doc.name} exists for user")

        self._repo.save(doc)
        return doc

    def update(self, doc: Resource) -> Resource:
        # Guard against name conflicts with other resources
        existing_with_name = self._repo.find_by_name(doc.identity, doc.category, doc.type, doc.name)
        if existing_with_name and existing_with_name.rid != doc.rid:
            raise ValueError(f"{doc.category}:{doc.type}:{doc.name} exists for user")

        doc.version += 1
        doc.updated = datetime.now(timezone.utc)
        self._repo.update(doc)
        return doc

    def delete(self, rid: str) -> None:
        direct_bps = self._bp_repo.list_direct_usage(rid)
        nested_res = self._repo.list_nested_usage(rid)

        if direct_bps or nested_res:
            raise ResourceInUseError(by_blueprints=direct_bps,
                                     by_resources=nested_res)
        self._repo.delete(rid)

    def list_nested_usage(self, rid: str) -> List[str]:
        """Return resource IDs whose `nested_refs` array contains *rid*."""
        return self._repo.list_nested_usage(rid)

    # ---------- read ----------
    def get(self, rid: str) -> Resource:
        return self._repo.get(rid)

    def find_resources(self, query: ResourceQuery) -> Tuple[List[Resource], int]:
        """Find resources with pagination info."""
        resources = self._repo.find_resources(query)
        total_count = self._repo.count_resources(query)
        return resources, total_count

    def raw_config(self, rid: str) -> dict:
        """Return cfg_dict with encrypted string fields decrypted.

        Fetches the resource fresh from storage. Prefer ``raw_config_for``
        when the caller already has the ``Resource`` in hand, to avoid a
        redundant round-trip.
        """
        return self.raw_config_for(self.get(rid))

    def raw_config_for(self, resource: Resource) -> dict:
        """Return *resource*'s cfg_dict with encrypted string fields decrypted.

        Uses a shallow copy so the in-memory Resource is not mutated.
        FieldCipher.decrypt() is prefix-aware: non-encrypted values
        pass through unchanged, making this safe for all resource types.
        """
        cfg = dict(resource.cfg_dict)
        if self._cipher:
            for key, value in cfg.items():
                if isinstance(value, str):
                    cfg[key] = self._cipher.decrypt(value)
        return cfg

    def meta(self, rid: str) -> tuple[str, str]:
        return self._repo.meta(rid)

    def exists(self, rid: str) -> bool:
        return self._repo.exists(rid)

    def count_by_config_field(
        self,
        identity: Identity,
        field: str,
        value: str,
        exclude_rid: str = "",
    ) -> int:
        """Count resources where cfg_dict.<field> == value for the given owner identity."""
        return self._repo.count_by_config_field(identity, field, value, exclude_rid)

    def exists_by_name(
        self, identity: Identity, category: str, type_: str, name: str
    ) -> bool:
        return self._repo.find_by_name(identity, category, type_, name) is not None

    # ---------- statistics ----------
    def count(self, identity: Identity, filter: Dict[str, Any] | None = None) -> int:
        """Count resources matching filter criteria for an identity."""
        return self._repo.count(identity, filter or {})

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] | None = None,
    ) -> List[GroupedCount]:
        """
        Group resources by specified fields and return counts.
        Performs efficient server-side grouping via the repository.
        """
        return self._repo.group_count(identity, group_by, filter)
