from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Dict, FrozenSet

from mas.core.enums import ResourceCategory
from mas.resources.deletion.context import DeletionContext
from mas.resources.deletion.mode import DeleteMode


class DeleteStrategy(ABC):
    """
    Base class for force-delete algorithms.

    Subclasses declare mode + categories via ClassVars.
    Auto-discovered via build_strategy_map().
    """

    mode: ClassVar[DeleteMode]
    categories: ClassVar[FrozenSet[ResourceCategory]]

    def validate(self, ctx: DeletionContext) -> None:
        """Pre-execution validation. Override for strategy-specific checks."""
        pass

    @abstractmethod
    def execute(self, ctx: DeletionContext) -> None:
        """Rewrite inbound references. The service deletes the resource afterwards."""
        ...

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
        if not ctx.replacement_rid:
            raise ValueError("replacementId is required for replace mode")
        mapping = {ctx.resource.rid: ctx.replacement_rid}
        ctx.registry.remap_nested_refs(ctx.resource.rid, mapping)
        for bp_id in ctx.blueprint_ids:
            ctx.bp_refs.remap_refs(bp_id, mapping)


class DetachStrategy(DeleteStrategy):
    """Remove all references from dependents."""

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
    """Delete dependent blueprints and clean remaining references."""

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
