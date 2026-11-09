from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Dict, FrozenSet

from mas.core.enums import ResourceCategory
from mas.resources.deletion.context import DeletionContext
from mas.resources.deletion.mode import DeleteMode
from mas.resources.models import Resource

logger = logging.getLogger(__name__)


class DeleteStrategy(ABC):
    """
    Base class for force-delete algorithms.

    Subclasses declare mode + categories via ClassVars.
    Auto-discovered via build_strategy_map().
    """

    mode: ClassVar[DeleteMode]
    categories: ClassVar[FrozenSet[ResourceCategory]]

    @classmethod
    def build_strategy_map(cls) -> Dict[ResourceCategory, "DeleteStrategy"]:
        """Auto-discover concrete subclasses and build {category -> strategy}."""
        mapping: Dict[ResourceCategory, DeleteStrategy] = {}
        for strategy_cls in cls.__subclasses__():
            instance = strategy_cls()
            for cat in strategy_cls.categories:
                if cat in mapping:
                    raise ValueError(
                        f"Category {cat!r} claimed by both "
                        f"{type(mapping[cat]).__name__} and "
                        f"{strategy_cls.__name__}"
                    )
                mapping[cat] = instance
        return mapping

    def validate(self, ctx: DeletionContext) -> None:
        """Pre-execution validation. Override for strategy-specific checks."""
        pass

    @abstractmethod
    def execute(self, ctx: DeletionContext) -> None:
        """Rewrite inbound references.

        Detach and cascade leave deletion to the service. Replace deletes
        inside execute so that step can roll back with the remaps.
        """
        ...


class ReplaceStrategy(DeleteStrategy):
    """Swap all references to a replacement."""

    mode = DeleteMode.REPLACE
    categories = frozenset({ResourceCategory.LLM, ResourceCategory.CONDITION})

    def validate(self, ctx: DeletionContext) -> None:
        if not ctx.replacement_rid:
            raise ValueError("replacementId is required for replace mode")
        if ctx.replacement_rid == ctx.resource.rid:
            raise ValueError("Replacement cannot be the same as the resource")
        replacement = ctx.registry.get(ctx.replacement_rid)
        if ctx.resource.category != replacement.category:
            raise ValueError(
                f"Replacement must be the same category "
                f"(got {replacement.category}, expected {ctx.resource.category})"
            )

    def execute(self, ctx: DeletionContext) -> None:
        """Remap dependents and delete the target, restoring snapshots on failure.

        Repositories do not share a transaction. Completed remaps are written
        back from pre-images when a later remap or ``commit_delete`` fails,
        including reinserting the original resource if the delete removed it.
        """
        if not ctx.replacement_rid:
            raise ValueError("replacementId is required for replace mode")
        if ctx.commit_delete is None:
            raise RuntimeError("replace mode requires commit_delete")

        mapping = {ctx.resource.rid: ctx.replacement_rid}
        snapshots = _capture_replace_snapshots(ctx)
        try:
            ctx.registry.remap_nested_refs(ctx.resource.rid, mapping)
            for bp_id in ctx.blueprint_ids:
                ctx.bp_refs.remap_refs(bp_id, mapping)
            ctx.commit_delete()
        except Exception:
            _restore_replace_snapshots(ctx, snapshots)
            raise


class DetachStrategy(DeleteStrategy):
    """Remove all references from dependents.

    No snapshot/rollback: a mid-loop failure can leave partial strips.
    That is accepted — unlike replace, the target is not deleted inside
    execute, and a partial strip is still a valid (if incomplete) detach.
    """

    mode = DeleteMode.DETACH
    categories = frozenset(
        {
            ResourceCategory.TOOL,
            ResourceCategory.PROVIDER,
            ResourceCategory.RETRIEVER,
            ResourceCategory.SANDBOX,
        }
    )

    def execute(self, ctx: DeletionContext) -> None:
        _strip_all_refs(ctx, blueprint_ids=ctx.blueprint_ids)


class CascadeStrategy(DeleteStrategy):
    """Delete dependent blueprints and clean remaining references.

    No snapshot/rollback: a mid-loop failure can leave some blueprints
    already deleted. Same rationale as detach — the target delete stays
    in the service, after this rewrite.
    """

    mode = DeleteMode.CASCADE
    categories = frozenset({ResourceCategory.NODE})

    def execute(self, ctx: DeletionContext) -> None:
        for bp_id in ctx.blueprint_ids:
            ctx.bp_refs.delete(bp_id)
        # Blueprints that referenced rid are gone; only strip nested resources.
        _strip_all_refs(ctx, blueprint_ids=[])


def _strip_all_refs(
    ctx: DeletionContext,
    *,
    blueprint_ids: list[str],
) -> None:
    """Remove rid from nested resources and from the given blueprint ids."""
    ctx.registry.strip_nested_refs(ctx.resource.rid)
    for bp_id in blueprint_ids:
        ctx.bp_refs.strip_refs(bp_id, ctx.resource.rid)


@dataclass(frozen=True)
class _ReplaceSnapshots:
    target: Resource
    resources: tuple[Resource, ...]
    blueprints: tuple[tuple[str, dict, list[str]], ...]


def _capture_replace_snapshots(ctx: DeletionContext) -> _ReplaceSnapshots:
    resources = tuple(
        ctx.registry.get(dep_id).model_copy(deep=True)
        for dep_id in ctx.registry.list_nested_usage(ctx.resource.rid)
    )
    blueprints = tuple(
        (bp_id, *ctx.bp_refs.capture_spec(bp_id))
        for bp_id in ctx.blueprint_ids
    )
    return _ReplaceSnapshots(
        target=ctx.resource.model_copy(deep=True),
        resources=resources,
        blueprints=blueprints,
    )


def _restore_replace_snapshots(ctx: DeletionContext, snapshots: _ReplaceSnapshots) -> None:
    for doc in snapshots.resources:
        try:
            ctx.registry.restore_snapshot(doc)
        except Exception:
            logger.exception(
                "Failed to restore resource %s during replace rollback", doc.rid
            )
    for bp_id, spec_dict, rid_refs in snapshots.blueprints:
        try:
            ctx.bp_refs.restore_spec(bp_id, spec_dict, rid_refs)
        except Exception:
            logger.exception(
                "Failed to restore blueprint %s during replace rollback", bp_id
            )
    try:
        ctx.registry.restore_snapshot(snapshots.target)
    except Exception:
        logger.exception(
            "Failed to restore resource %s during replace rollback",
            snapshots.target.rid,
        )
