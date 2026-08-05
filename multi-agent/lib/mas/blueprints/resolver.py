from dataclasses import dataclass, field
from typing import TypeVar, Any, Dict, Tuple
from pydantic import BaseModel
from mas.core.enums import ResourceCategory
from mas.core.caller_scope import CallerScope
from mas.core.ref.models import Ref
from mas.core.ref import RefWalker
from .models.blueprint import (
    BlueprintResource,
    ResourceSpec,
    BlueprintDraft,
    BlueprintSpec
)
from mas.resources.ports import ResourceReader

T = TypeVar("T", bound=BaseModel)


@dataclass
class _ResolveSession:
    """Mutable per-call state for one ``resolve()``/``resolve_tolerant()`` invocation.

    Bundling this alongside ``CallerScope`` is what lets the internal walk
    helpers (``_stash_inline``/``_walk_live``/``_scan_nested``) take a single
    extra parameter instead of six, no matter how much per-call state this
    grows in the future.
    """
    caller: CallerScope
    bucket: dict[str, list] = field(default_factory=dict)
    visited: set[str] = field(default_factory=set)
    broken_refs: Dict[str, str] = field(default_factory=dict)
    strict: bool = True


class BlueprintResolver:
    def __init__(self, resources_service: ResourceReader) -> None:
        self.resources_service = resources_service
        # Removed instance variables to make thread-safe:
        # session state is now local to each resolve() call

    def resolve(
        self, draft: BlueprintDraft, caller: CallerScope = CallerScope(),
    ) -> BlueprintSpec:
        """Resolve a draft into an executable spec.

        ``caller.identity`` is the caller/session owner. When set, any
        external Ref to a built-in resource is resolved through
        ``ResourcesService.resolve()``, which merges the caller's
        ``builtin_user_configs`` overlay on top of the resource's defaults.
        Without it (e.g. schema-only tooling), built-ins resolve to their
        raw defaults — the same behavior as before overlays existed.

        ``caller.is_admin`` gates draft-builtin visibility the same way it
        does elsewhere (``ResourcesService.get_visible``) — a non-admin
        caller's external ref to a draft built-in is treated as not found
        rather than resolved.

        Raises ``KeyError`` if any referenced resource no longer exists.
        Use ``resolve_tolerant`` when broken refs should be reported
        rather than raised (e.g. blueprint validation).
        """
        spec, _broken_refs = self._resolve(draft, caller, strict=True)
        return spec

    def resolve_tolerant(
        self, draft: BlueprintDraft, caller: CallerScope = CallerScope(),
    ) -> Tuple[BlueprintSpec, Dict[str, str]]:
        """Like ``resolve``, but never raises for a missing referenced resource.

        Unresolvable external refs are skipped (left out of the returned
        spec) and reported in the second return value as ``{rid: reason}``,
        so callers — namely blueprint validation — can surface them as
        per-element failures instead of aborting the whole request.
        """
        return self._resolve(draft, caller, strict=False)

    # --------------------------------------------------------------------
    # helpers
    # --------------------------------------------------------------------
    def _resolve(
        self, draft: BlueprintDraft, caller: CallerScope, strict: bool,
    ) -> Tuple[BlueprintSpec, Dict[str, str]]:
        # Create local session for this resolution (thread-safe)
        session = _ResolveSession(caller=caller, strict=strict)

        # --- walk every catalogue in the draft ---------------------------
        for cat in list(ResourceCategory):
            for res in getattr(draft, cat.value):
                raw_rid = res.rid.ref if isinstance(res.rid, Ref) else res.rid

                external_ref = isinstance(res.rid, Ref) and res.rid.is_external_ref()

                if not external_ref:
                    # inline resource → keep its config in the bucket
                    self._stash_inline(cat, res, session)
                else:  # ← LIVE REF
                    # external Ref → fetch from registry
                    self._walk_live(raw_rid, res.name, session)

        # --- build executable spec ---------------------------------------
        spec = BlueprintSpec(
            **{cat.value: session.bucket.get(cat.value, []) for cat in list(ResourceCategory)},
            plan=draft.plan,
            name=draft.name,
            description=draft.description,
        )
        return spec, session.broken_refs

    # --------------------------------------------------------------------
    # helpers
    # --------------------------------------------------------------------
    def _stash_inline(
        self, cat: ResourceCategory, res: BlueprintResource, session: _ResolveSession,
    ) -> None:
        """Put an inline/frozen entry straight into the bucket."""
        concrete = res.config  # already a validated Pydantic model
        session.bucket.setdefault(cat.value, []).append(
            ResourceSpec[type(concrete)](
                rid=res.rid, name=res.name, type=res.type, config=concrete
            )
        )
        # still inspect it for nested rids
        self._scan_nested(concrete, session)

    def _walk_live(
        self, rid: str, name: str | None, session: _ResolveSession,
    ) -> None:
        """Fetch a live resource (with built-in overlay applied) and recurse.

        Uses ``get_visible`` rather than a plain ``get`` so a non-admin
        caller's ref to a draft built-in is treated the same as a missing
        resource (KeyError) instead of resolving its config.
        """
        if rid in session.visited:
            return
        session.visited.add(rid)

        try:
            resource = self.resources_service.get_visible(rid, caller=session.caller)
        except KeyError:
            if session.strict:
                raise
            session.broken_refs[rid] = f"Referenced resource not found: {rid}"
            return

        obj = self.resources_service.resolve_resource(resource, session.caller)
        cat = resource.category.value if hasattr(resource.category, "value") else resource.category
        name = name if name is not None else resource.name

        session.bucket.setdefault(cat, []).append(
            ResourceSpec[type(obj)](rid=rid, name=name, type=resource.type, config=obj)
        )
        self._scan_nested(obj, session)

    def _scan_nested(self, node: Any, session: _ResolveSession) -> None:
        """
        Recursively walk any BaseModel, dict, list/tuple or Ref.
        Whenever we hit an external Ref, call _walk_live.
        """
        for child_rid in RefWalker.external_rids(node):
            self._walk_live(child_rid, None, session)
