"""
ResourceMaterializer - Saves blueprint resources and creates $ref-based blueprint.

Converts a BlueprintDraft with inline configs into:
1. Saved resources in user's account
2. BlueprintDraft with $ref references

SOLID:
- Single Responsibility: Orchestrates resource saving and blueprint building
- Open/Closed: Works with any ResourceCategory
- Dependency Inversion: Depends on ResourcesService abstraction
"""
from typing import Dict, List
from uuid import uuid4

from mas.core.identity import Identity
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintResource, StepDef
from mas.resources.service import ResourcesService
from mas.resources.models import Resource
from mas.core.ref import RefRemapper
from mas.core.ref.models import Ref
from mas.core.enums import ResourceCategory, SystemNodeType
from mas.templates.errors import MaterializationError
from mas.templates.instantiation.models import CollectedResource, MaterializationResult


class ResourceMaterializer:
    """
    Materializes inline blueprint resources to saved resources.
    
    Flow:
    1. Collect inline resources, assign final_rids
    2. Remap Ref objects in configs
    3. Save resources (with rollback on failure)
    4. Build final blueprint with $ref entries
    """

    UNIQUE_SUFFIX_LENGTH = 8

    def __init__(self, resources_service: ResourcesService):
        self._resources = resources_service

    def materialize(self, draft: BlueprintDraft, identity: Identity) -> MaterializationResult:
        """Materialize inline resources and build final blueprint."""
        # Step 1: Collect inline resources
        collected = self._collect_inline_resources(draft)

        if not collected:
            return MaterializationResult(blueprint_draft=draft)

        # Derive id_mapping from collected
        id_mapping = {c.template_rid: c.final_rid for c in collected}

        # Step 2: Remap Ref objects in configs
        self._remap_configs(collected, id_mapping)

        # Step 3 & 4: Save and build (single rollback point)
        saved_rids: List[str] = []
        try:
            saved_rids = self._save_resources(collected, identity)
            final_draft = self._build_final_draft(draft, id_mapping)
        except Exception as e:
            self._rollback(saved_rids)
            raise MaterializationError(f"Materialization failed: {e}", errors=[])

        return MaterializationResult(
            blueprint_draft=final_draft,
            resource_ids=saved_rids,
            id_mapping=id_mapping,
        )

    # ─────────────────────────────────────────────────────────────────────
    #  Step 1: Collect
    # ─────────────────────────────────────────────────────────────────────
    def _collect_inline_resources(self, draft: BlueprintDraft) -> List[CollectedResource]:
        """Collect inline resources that need to be saved."""
        collected = []
        for category in ResourceCategory:
            for bp_resource in getattr(draft, category.value, []):
                if self._should_save(bp_resource):
                    collected.append(CollectedResource(
                        template_rid=bp_resource.rid.ref,
                        final_rid=uuid4().hex,
                        category=category,
                        bp_resource=bp_resource,
                    ))
        return collected

    def _should_save(self, bp_resource: BlueprintResource) -> bool:
        """Check if resource should be saved (not system, has config, not external)."""
        return (
                bp_resource.config is not None
                and not bp_resource.rid.is_external_ref()
                and bp_resource.type not in SystemNodeType.values()
        )

    # ─────────────────────────────────────────────────────────────────────
    #  Step 2: Remap
    # ─────────────────────────────────────────────────────────────────────
    def _remap_configs(self, collected: List[CollectedResource], id_mapping: Dict[str, str]) -> None:
        """Remap Ref objects in configs to final_rids."""
        prefixed = {k: Ref.make_external(v) for k, v in id_mapping.items()}
        for item in collected:
            if item.bp_resource.config:
                item.bp_resource.config = RefRemapper.remap(item.bp_resource.config, prefixed)

    # ─────────────────────────────────────────────────────────────────────
    #  Step 3: Save
    # ─────────────────────────────────────────────────────────────────────
    def _save_resources(self, collected: List[CollectedResource], identity: Identity) -> List[str]:
        """Save resources one by one. Returns saved rids. Caller handles rollback."""
        suffix = uuid4().hex[:self.UNIQUE_SUFFIX_LENGTH]
        saved_rids = []

        for item in collected:
            resource = Resource(
                rid=item.final_rid,
                identity=identity,
                category=item.category,
                type=item.bp_resource.type or "",
                name=f"{item.bp_resource.name or item.bp_resource.type}_{suffix}",
                cfg_dict=item.bp_resource.config.model_dump(mode="json"),
                nested_refs=[],
            )
            self._resources.save_resource(resource)
            saved_rids.append(resource.rid)

        return saved_rids

    def _rollback(self, rids: List[str]) -> None:
        """Best-effort cleanup of saved resources."""
        for rid in rids:
            try:
                self._resources.delete(rid)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────
    #  Step 4: Build Final Draft
    # ─────────────────────────────────────────────────────────────────────
    def _build_final_draft(self, draft: BlueprintDraft, id_mapping: Dict[str, str]) -> BlueprintDraft:
        """Build draft with $ref entries for saved resources."""
        return BlueprintDraft(
            nodes=self._remap_entries(draft.nodes, id_mapping),
            conditions=self._remap_entries(draft.conditions, id_mapping),
            llms=[],
            retrievers=[],
            tools=[],
            providers=[],
            plan=self._remap_plan(draft.plan, id_mapping),
            name=draft.name,
            description=draft.description,
        )

    def _remap_entries(
            self,
            entries: List[BlueprintResource],
            id_mapping: Dict[str, str],
    ) -> List[BlueprintResource]:
        """Replace saved resources with $ref, keep system nodes inline."""
        result = []
        for entry in entries:
            template_rid = entry.rid.ref
            if template_rid in id_mapping:
                # Saved → $ref entry using clean method
                result.append(BlueprintResource(
                    rid=entry.rid.to_external(id_mapping[template_rid])
                ))
            else:
                # System node → keep as-is
                result.append(entry)
        return result

    def _remap_plan(self, plan: List[StepDef], id_mapping: Dict[str, str]) -> List[StepDef]:
        """Remap plan refs to final_rids."""
        return [self._remap_step(step, id_mapping) for step in plan]

    def _remap_step(self, step: StepDef, id_mapping: Dict[str, str]) -> StepDef:
        """Remap a single step's references."""
        node_rid = step.node.ref
        new_node = type(step.node)(id_mapping.get(node_rid, node_rid))

        new_condition = None
        if step.exit_condition:
            cond_rid = step.exit_condition.ref
            new_condition = type(step.exit_condition)(id_mapping.get(cond_rid, cond_rid))

        return StepDef(
            uid=step.uid,
            after=step.after,
            node=new_node,
            exit_condition=new_condition,
            branches=step.branches,
            meta=step.meta,
        )
