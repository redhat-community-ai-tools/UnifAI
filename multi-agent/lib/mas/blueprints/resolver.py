from typing import TypeVar, Any
from pydantic import BaseModel
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.core.ref.models import Ref
from mas.core.ref import RefWalker
from .models.blueprint import (
    BlueprintResource,
    ResourceSpec,
    BlueprintDraft,
    BlueprintSpec
)
from mas.resources.service import ResourcesService

T = TypeVar("T", bound=BaseModel)


class BlueprintResolver:
    def __init__(self, resources_service: ResourcesService):
        self.resources_service = resources_service
        # Removed instance variables to make thread-safe:
        # _visited and _bucket are now local to each resolve() call

    def resolve(self, draft: BlueprintDraft, identity: Identity = None) -> BlueprintSpec:
        """Resolve a draft into an executable spec.

        ``identity`` is the caller/session owner. When provided, any
        external Ref to a built-in resource is resolved through
        ``ResourcesService.resolve()``, which merges the caller's
        ``builtin_user_configs`` overlay on top of the resource's defaults.
        Without it (e.g. schema-only tooling), built-ins resolve to their
        raw defaults — the same behavior as before overlays existed.
        """
        # Create local state for this resolution (thread-safe)
        bucket: dict[str, list] = {}
        visited: set[str] = set()

        # --- walk every catalogue in the draft ---------------------------
        for cat in list(ResourceCategory):
            for res in getattr(draft, cat.value):
                raw_rid = res.rid.ref if isinstance(res.rid, Ref) else res.rid

                external_ref = isinstance(res.rid, Ref) and res.rid.is_external_ref()

                if not external_ref:
                    # inline resource → keep its config in the bucket
                    self._stash_inline(cat, res, bucket, visited, identity)
                else:  # ← LIVE REF
                    # external Ref → fetch from registry
                    self._walk_live(raw_rid, res.name, bucket, visited, identity)

        # --- build executable spec ---------------------------------------
        return BlueprintSpec(
            **{cat.value: bucket.get(cat.value, []) for cat in list(ResourceCategory)},
            plan=draft.plan,
            name=draft.name,
            description=draft.description,
        )

    # --------------------------------------------------------------------
    # helpers
    # --------------------------------------------------------------------
    def _stash_inline(
        self, cat: ResourceCategory, res: BlueprintResource, bucket: dict, visited: set,
        identity: Identity = None,
    ):
        """Put an inline/frozen entry straight into the bucket."""
        concrete = res.config  # already a validated Pydantic model
        bucket.setdefault(cat.value, []).append(
            ResourceSpec[type(concrete)](
                rid=res.rid, name=res.name, type=res.type, config=concrete
            )
        )
        # still inspect it for nested rids
        self._scan_nested(concrete, bucket, visited, identity)

    def _walk_live(
        self, rid: str, name: str | None, bucket: dict, visited: set,
        identity: Identity = None,
    ):
        """Fetch a live resource (with built-in overlay applied) and recurse."""
        if rid in visited:
            return
        visited.add(rid)

        resource = self.resources_service.get(rid)
        obj = self.resources_service.resolve(rid, identity=identity)
        cat = resource.category.value if hasattr(resource.category, "value") else resource.category
        name = resource.name

        bucket.setdefault(cat, []).append(
            ResourceSpec[type(obj)](rid=rid, name=name, type=resource.type, config=obj)
        )
        self._scan_nested(obj, bucket, visited, identity)

    def _scan_nested(self, node: Any, bucket: dict, visited: set, identity: Identity = None):
        """
        Recursively walk any BaseModel, dict, list/tuple or Ref.
        Whenever we hit an external Ref, call _walk_live.
        """
        for child_rid in RefWalker.external_rids(node):
            self._walk_live(child_rid, None, bucket, visited, identity)
