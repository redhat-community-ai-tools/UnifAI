from __future__ import annotations

from typing import Optional

from pydantic import ValidationError

from mas.blueprints.ref_service import BlueprintRefService
from mas.collaboration.service import EditLockKind
from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceCategory
from mas.resources.deletion.context import DeletionContext
from mas.resources.deletion.mode import DeleteMode
from mas.resources.deletion.models import (
    BlueprintUsageDetail,
    ResourceUsageDetail,
    UsageCheckResult,
)
from mas.resources.deletion.strategies import DeleteStrategy
from mas.resources.errors import ResourceInUseError, ResourceLockedError
from mas.resources.ports import DependentEditLockReader, ResourceServicePort
from mas.resources.registry import ResourcesRegistry


class ResourceDeletionService:
    """
    Orchestrates force-deletion of in-use resources and enriched usage checks.

    Strategies are auto-discovered from DeleteStrategy subclasses
    via build_strategy_map().
    """

    def __init__(
        self,
        registry: ResourcesRegistry,
        bp_refs: BlueprintRefService,
        resources: ResourceServicePort,
        lock_reader: Optional[DependentEditLockReader] = None,
    ):
        self._registry = registry
        self._bp_refs = bp_refs
        self._resources = resources
        self._lock_reader = lock_reader
        self._strategies = DeleteStrategy.build_strategy_map()

    @staticmethod
    def _parse_mode(mode: str) -> DeleteMode:
        try:
            return DeleteMode(mode)
        except ValueError:
            raise ValueError(
                f"Unknown mode: {mode}. "
                f"Must be one of: {', '.join(m.value for m in DeleteMode)}"
            ) from None

    def check_usage(self, rid: str) -> UsageCheckResult:
        """Check whether a resource is in use and how it can be force-deleted."""
        resource = self._registry.get(rid)
        bp_ids, res_ids = self._registry.check_usage(rid)

        if not bp_ids and not res_ids:
            return UsageCheckResult(in_use=False)

        strategy = self._strategy_for(ResourceCategory(resource.category))
        return UsageCheckResult(
            in_use=True,
            category=resource.category,
            allowed_mode=strategy.mode,
            blueprints=self._enrich_blueprints(bp_ids),
            resources=self._enrich_resources(res_ids),
        )

    def usage_payload_for_in_use(self, rid: str, err: ResourceInUseError) -> UsageCheckResult:
        """Build the 409 body from a fresh usage check, or from *err* if that misses."""
        try:
            current = self.check_usage(rid)
        except KeyError:
            current = None

        if current is not None and current.in_use:
            return current
        return self._usage_from_in_use_error(rid, err)

    def force_delete(
        self,
        rid: str,
        mode: str,
        replacement_rid: Optional[str] = None,
        *,
        caller: CallerScope,
        username: str = "",
    ) -> None:
        """Authorize the caller, rewrite references, then delete through the resource facade."""
        self._resources.guard_write_access(rid, caller, username=username)

        requested_mode = self._parse_mode(mode)
        resource = self._registry.get(rid)
        strategy = self._strategy_for(ResourceCategory(resource.category))

        if requested_mode != strategy.mode:
            raise ValueError(
                f"Mode '{mode}' is not permitted for {resource.category} "
                f"resources. Use '{strategy.mode.value}' instead."
            )

        if requested_mode == DeleteMode.REPLACE and replacement_rid:
            self._resources.get_visible(replacement_rid, caller=caller)

        bp_ids, res_ids = self._registry.check_usage(rid)
        ctx = DeletionContext(
            resource=resource,
            replacement_rid=replacement_rid,
            blueprint_ids=bp_ids,
            registry=self._registry,
            bp_refs=self._bp_refs,
            commit_delete=lambda: self._resources.delete(rid),
        )

        strategy.validate(ctx)
        self._reject_if_dependents_locked(
            caller=caller,
            username=username,
            blueprint_ids=bp_ids,
            resource_ids=res_ids,
        )
        strategy.execute(ctx)
        # ReplaceStrategy deletes through commit_delete so a failure can
        # restore remaps and the original resource. Other strategies only
        # rewrite; the facade delete (credential and built-in cleanup) stays here.
        if requested_mode != DeleteMode.REPLACE:
            self._resources.delete(rid)

    def _strategy_for(self, category: ResourceCategory) -> DeleteStrategy:
        if category not in self._strategies:
            raise ValueError(f"No delete strategy registered for category: {category.value}")
        return self._strategies[category]

    def _reject_if_dependents_locked(
        self,
        *,
        caller: CallerScope,
        username: str,
        blueprint_ids: list[str],
        resource_ids: list[str],
    ) -> None:
        """Block rewrite when a teammate holds an edit lock on a dependent."""
        if self._lock_reader is None:
            return
        identity = caller.identity
        if identity is None or not identity.is_team:
            return

        team_id = identity.id
        for kind, ids in (
            (EditLockKind.BLUEPRINT.value, blueprint_ids),
            (EditLockKind.RESOURCE.value, resource_ids),
        ):
            if not ids:
                continue
            holders = self._lock_reader.get_team_edit_locks_batch(team_id, kind, ids)
            for holder in holders.values():
                if holder is None:
                    continue
                if username and holder.user_id.casefold() == username.casefold():
                    continue
                raise ResourceLockedError(
                    locked_by_user_id=holder.user_id,
                    locked_by_display_name=holder.display_name,
                )

    def _usage_from_in_use_error(self, rid: str, err: ResourceInUseError) -> UsageCheckResult:
        category: Optional[str] = None
        allowed_mode: Optional[DeleteMode] = None
        try:
            resource = self._registry.get(rid)
            category = resource.category
            allowed_mode = self._strategy_for(ResourceCategory(category)).mode
        except (KeyError, ValueError):
            pass

        return UsageCheckResult(
            in_use=True,
            category=category,
            allowed_mode=allowed_mode,
            blueprints=self._enrich_blueprints(list(err.by_blueprints)),
            resources=self._enrich_resources(list(err.by_resources)),
        )

    def _enrich_blueprints(self, bp_ids: list) -> list[BlueprintUsageDetail]:
        result: list[BlueprintUsageDetail] = []
        for bp_id in bp_ids:
            try:
                summary = self._bp_refs.get_summary(bp_id)
                result.append(BlueprintUsageDetail(id=summary.id, name=summary.name))
            except (KeyError, ValidationError):
                result.append(BlueprintUsageDetail(id=bp_id, name=bp_id))
        return result

    def _enrich_resources(self, res_ids: list) -> list[ResourceUsageDetail]:
        result: list[ResourceUsageDetail] = []
        for res_id in res_ids:
            try:
                res = self._registry.get(res_id)
                result.append(
                    ResourceUsageDetail(
                        id=res_id,
                        name=res.name,
                        category=res.category,
                        type=res.type,
                    )
                )
            except KeyError:
                result.append(ResourceUsageDetail(id=res_id, name=res_id))
        return result
