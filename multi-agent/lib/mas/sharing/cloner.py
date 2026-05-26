import logging
from typing import Dict, List, Tuple, Set, Optional, Any
from uuid import uuid4
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel

from mas.core.identity import Identity
from mas.resources.models import Resource
from mas.resources.registry import ResourcesRegistry
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintResource, StepDef
from mas.blueprints.service import BlueprintService
from mas.catalog.element_registry import ElementRegistry
from mas.core.ref import RefWalker, RefRemapper
from mas.core.ref.models import Ref
from mas.core.enums import ResourceCategory

logger = logging.getLogger(__name__)


@dataclass
class ResourceCacheData:
    """Cached data for a resource."""
    doc: Resource
    dependencies: Set[str]  # Pre-computed dependencies
    cfg_model: object  # Pre-built schema model


@dataclass
class CloneResult:
    """Result of a cloning operation with comprehensive metrics."""
    success: bool
    new_item_id: Optional[str] = None
    rid_mapping: Dict[str, str] = field(default_factory=dict)
    name_conflicts: Dict[str, str] = field(default_factory=dict)
    resources_cloned: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CloneContext:
    """
    Resolved identity context for a cloning operation.

    The service layer is responsible for building this — it owns the concerns
    of who the recipient is and how the sender should be displayed.  The cloner
    receives this as an opaque bundle and never needs to reason about users.

    Attributes:
        sender_id:             Primary sender identity id used for display / logging.
        recipient_id:          The user/team id who will own all cloned resources/blueprints.
        authorized_owner_ids:  Full set of identity ids authorised to be the resource owner.
                               When empty the cloner falls back to ``{sender_id}``.
                               For team shares this should include both the team id and the
                               individual user, so resources owned by either are accepted.
        is_team_contribution:  When True the share targets a team workspace and
                               sender_id is recorded as the contributor.
    """
    sender_id: str
    recipient_id: str
    sender_display_name: Optional[str] = None
    authorized_owner_ids: frozenset = field(default_factory=frozenset)
    is_team_contribution: bool = False

    def is_authorized_owner(self, identity_id: str) -> bool:
        """Return True when *identity_id* is allowed to be the resource owner."""
        pool = self.authorized_owner_ids or frozenset({self.sender_id})
        return identity_id in pool

    @property
    def contributed_by(self) -> Optional[str]:
        return self.sender_id if self.is_team_contribution else None

    @property
    def sender_label(self) -> str:
        return self.sender_display_name or self.sender_id


class ShareCloner:
    """
    Efficient cloner for sharing resources and blueprints.
    
    Features:
    - Accurate dependency discovery with RefWalker
    - Single-pass loading and caching for efficiency  
    - Type-safe reference replacement with proper Ref handling
    - Automatic step UID regeneration for conflict avoidance
    - Comprehensive error handling and logging
    """

    def __init__(self,
                 resources_registry: ResourcesRegistry,
                 blueprint_service: BlueprintService,
                 element_registry: ElementRegistry):
        self.resources = resources_registry
        self.blueprints = blueprint_service
        self.elements = element_registry

    @staticmethod
    def _recipient_identity(ctx: CloneContext) -> Identity:
        """Build the correct Identity for the recipient of a share."""
        if ctx.is_team_contribution:
            return Identity.team(ctx.recipient_id)
        return Identity.user(ctx.recipient_id)

    def clone_resource_graph(self, *, root_rid: str, ctx: CloneContext) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Clone resource and all its dependencies."""
        logger.info(f"Starting resource graph clone: {root_rid} from {ctx.sender_id} to {ctx.recipient_id}")

        # Single pass: Load resources + compute dependencies + cache models
        closure_data = self._compute_closure({root_rid}, ctx)

        # Clone using pre-computed data
        result = self._clone_resource_set(closure_data, ctx)

        if not result.success:
            raise ValueError(f"Resource cloning failed: {result.errors}")

        logger.info(f"Resource graph clone completed: {result.resources_cloned} resources cloned")
        return result.rid_mapping, result.name_conflicts

    def clone_blueprint(self, *, blueprint_id: str, ctx: CloneContext) -> Tuple[str, Dict[str, str], Dict[str, str]]:
        """Clone blueprint and all its dependencies."""
        logger.info(f"Starting blueprint clone: {blueprint_id} from {ctx.sender_id} to {ctx.recipient_id}")

        try:
            # Load and validate blueprint
            bp_doc = self.blueprints.get_blueprint_draft_doc(blueprint_id)
            if not ctx.is_authorized_owner(bp_doc.identity.id):
                raise ValueError(f"Blueprint {blueprint_id} not owned by sender")

            draft = BlueprintDraft(**bp_doc.spec_dict)
            # Union stored rid_refs with a fresh walk of the draft (avoids stale rid_refs).
            external_rids = set(bp_doc.rid_refs or [])
            external_rids |= RefWalker.external_rids(draft)
            recipient = self._recipient_identity(ctx)

            # Clone dependencies and build RID mapping
            rid_mapping, name_conflicts, resources_cloned = self._clone_dependencies(
                external_rids, ctx
            )

            # Clone blueprint with proper ref handling and new step UIDs
            new_draft = self._clone_blueprint_draft(draft, rid_mapping, ctx)

            # Build metadata for the cloned blueprint
            bp_metadata = {}
            if ctx.is_team_contribution:
                bp_metadata["contributed_by"] = ctx.sender_id

            new_blueprint_id = self.blueprints.save_draft(
                identity=recipient,
                draft_dict=new_draft.model_dump(mode="json"),
                metadata=bp_metadata or None,
            )

            logger.info(f"Blueprint clone completed: {new_blueprint_id}, {resources_cloned} resources cloned")
            return new_blueprint_id, rid_mapping, name_conflicts

        except Exception as e:
            logger.error(f"Blueprint clone failed: {e}")
            raise

    def _clone_dependencies(self, external_rids: Set[str],
                            ctx: CloneContext) -> Tuple[Dict[str, str], Dict[str, str], int]:
        """Clone external dependencies and return mapping info."""
        if not external_rids:
            return {}, {}, 0

        logger.debug(f"Found external references: {external_rids}")

        closure_data = self._compute_closure(external_rids, ctx)

        if not closure_data:
            return {}, {}, 0

        logger.debug(f"Total closure to clone: {set(closure_data.keys())}")
        clone_result = self._clone_resource_set(closure_data, ctx)

        if not clone_result.success:
            raise ValueError(f"Failed to clone resources: {clone_result.errors}")

        logger.debug(f"RID mapping created: {clone_result.rid_mapping}")
        return clone_result.rid_mapping, clone_result.name_conflicts, clone_result.resources_cloned

    def _clone_resource_set(self, closure_data: Dict[str, ResourceCacheData],
                            ctx: CloneContext) -> CloneResult:
        """Clone a set of resources using pre-computed closure data."""
        try:
            logger.debug(f"Cloning {len(closure_data)} resources using cached data")

            # Generate RID mapping for all resources
            rid_mapping = {old_rid: uuid4().hex for old_rid in closure_data.keys()}
            name_conflicts = {}

            # Process each resource using cached data
            new_docs = []
            for old_rid, cache_data in closure_data.items():
                try:
                    new_doc = self._clone_single_resource(cache_data, rid_mapping, ctx)

                    # Track name conflicts
                    if new_doc.name != cache_data.doc.name:
                        name_conflicts[cache_data.doc.name] = new_doc.name

                    new_docs.append(new_doc)

                except Exception as e:
                    logger.error(f"Failed to clone resource {old_rid}: {e}")
                    return CloneResult(success=False, errors=[f"Failed to clone {old_rid}: {e}"])

            # Batch create all resources
            self._batch_create_resources(new_docs)

            return CloneResult(
                success=True,
                rid_mapping=rid_mapping,
                name_conflicts=name_conflicts,
                resources_cloned=len(new_docs)
            )

        except Exception as e:
            logger.error(f"Resource set clone failed: {e}")
            return CloneResult(success=False, errors=[str(e)])

    def _compute_closure(self, root_rids: Set[str], ctx: CloneContext) -> Dict[str, ResourceCacheData]:
        """
        Compute resource closure and cache all data in a single pass.

        Returns cached data for all resources in the dependency closure.
        Only includes resources owned by the sender.
        """
        visited_rids = set()
        to_visit = set(root_rids)
        closure_cache = {}

        while to_visit:
            rid = to_visit.pop()
            if rid in visited_rids:
                continue
            visited_rids.add(rid)

            try:
                # Load and validate resource
                doc = self.resources.get(rid)

                if not ctx.is_authorized_owner(doc.identity.id):
                    logger.warning(
                        f"Resource {rid} not owned by an authorized sender "
                        f"(owner={doc.identity.id}, authorized={ctx.authorized_owner_ids or {ctx.sender_id}})"
                    )
                    continue

                # Create schema model and compute dependencies
                cfg_model = self.elements.get_schema(
                    ResourceCategory(doc.category), doc.type
                )(**doc.cfg_dict)

                dependencies = RefWalker.external_rids(cfg_model)

                # Cache all computed data
                closure_cache[rid] = ResourceCacheData(
                    doc=doc,
                    dependencies=dependencies,
                    cfg_model=cfg_model
                )

                # Add new dependencies to traversal queue
                for dep_rid in dependencies:
                    if dep_rid not in visited_rids:
                        to_visit.add(dep_rid)

            except (KeyError, Exception) as e:
                logger.warning(f"Error processing resource {rid}: {e}")
                continue

        logger.debug(f"Cached data for {len(closure_cache)} resources")
        return closure_cache

    def _clone_single_resource(self, cache_data: ResourceCacheData,
                               rid_mapping: Dict[str, str],
                               ctx: CloneContext) -> Resource:
        """Clone a single resource using pre-computed data."""
        original_doc = cache_data.doc
        new_rid = rid_mapping[original_doc.rid]
        recipient = self._recipient_identity(ctx)

        new_name = self._resolve_name_conflict(
            recipient, original_doc.category,
            original_doc.type, original_doc.name, ctx
        )

        # Use typed model for clean remapping (Ref objects), then dump to dict
        remapped_model = RefRemapper.remap(cache_data.cfg_model, rid_mapping)
        new_cfg_dict = remapped_model.model_dump(mode="json")

        # Map dependencies to new RIDs
        new_nested_refs = [
            rid_mapping.get(dep_rid, dep_rid) for dep_rid in cache_data.dependencies
        ]

        return Resource(
            rid=new_rid,
            identity=recipient,
            category=original_doc.category,
            type=original_doc.type,
            name=new_name,
            version=1,
            cfg_dict=new_cfg_dict,
            nested_refs=new_nested_refs,
            contributed_by=ctx.contributed_by,
        )

    def _batch_create_resources(self, docs: List[Resource]) -> None:
        """Create multiple resources efficiently."""
        # TODO: Implement actual batch creation in ResourcesRegistry
        for doc in docs:
            self.resources.create(doc)

    def _resolve_name_conflict(self, identity: Identity, category: str,
                               type_: str, preferred_name: str,
                               ctx: CloneContext) -> str:
        """Resolve name conflicts.

        Team contributions keep the original name; user-to-user shares get a
        "(from <sender>)" suffix so the recipient can tell where it came from.
        """
        if ctx.is_team_contribution:
            base_name = preferred_name
        else:
            base_name = f"{preferred_name} (from {ctx.sender_label})"

        current_name = base_name

        for counter in range(2, 101):
            existing = self.resources.exists_by_name(identity, category, type_, current_name)
            if not existing:
                return current_name

            current_name = f"{base_name} ({counter})"

        # Fallback to UUID if too many conflicts
        return f"{base_name} ({uuid4().hex[:8]})"

    def _clone_blueprint_draft(self, draft: BlueprintDraft, rid_mapping: Dict[str, str],
                               ctx: CloneContext) -> BlueprintDraft:
        """Clone a BlueprintDraft with proper ref replacement and new step UIDs."""

        # Clone resource categories using ResourceCategory enum
        resource_fields = {
            category.value: [
                self._clone_resource_with_refs(res, rid_mapping)
                for res in getattr(draft, category.value)
            ]
            for category in ResourceCategory
        }

        if ctx.is_team_contribution:
            clone_name = draft.name
        else:
            clone_name = f"{draft.name} (from {ctx.sender_label})"

        return BlueprintDraft(
            plan=self._clone_plan(draft.plan, rid_mapping),
            name=clone_name,
            description=draft.description,
            **resource_fields
        )

    def _clone_resource_with_refs(self, resource: BlueprintResource, rid_mapping: Dict[str, str]) -> BlueprintResource:
        """Clone a resource and replace any Ref instances using shared utility."""
        return RefRemapper.remap(resource, rid_mapping)

    def _clone_plan(self, plan: List[StepDef], rid_mapping: Dict[str, str]) -> List[StepDef]:
        """Clone plan with proper UID mapping for step references."""
        if not plan:
            return []
        
        # Pass 1: Create UID mapping (old_uid -> new_uid)
        uid_mapping = {}
        cloned_steps = []
        
        for step in plan:
            # Clone step with new UID but keep original references for now
            cloned_step = step.model_copy(deep=True)
            new_uid = str(uuid4())
            
            # Store the mapping
            uid_mapping[step.uid] = new_uid
            cloned_step.uid = new_uid
            
            cloned_steps.append(cloned_step)
        
        # Pass 2: Update all step references and replace RIDs
        for step in cloned_steps:
            # Replace RIDs and UIDs in all fields except uid (which we already handled)
            manually_handled_fields = {"uid"}
            
            for field_name in step.model_fields:
                if field_name not in manually_handled_fields:
                    field_value = getattr(step, field_name, None)
                    if field_value is not None:
                        # First replace RIDs using shared utility, then replace UIDs
                        updated_value = RefRemapper.remap(field_value, rid_mapping)
                        updated_value = self._replace_step_uids(updated_value, uid_mapping)
                        setattr(step, field_name, updated_value)
        
        return cloned_steps

    def _replace_step_uids(self, obj: Any, uid_mapping: Dict[str, str]) -> Any:
        """Replace step UIDs in after/branches fields, including dict keys and values."""
        if isinstance(obj, str):
            # Replace if this string is a step UID
            return uid_mapping.get(obj, obj)
        
        elif isinstance(obj, list):
            # Handle list of step UIDs (like in after: ["step1", "step2"])
            return [self._replace_step_uids(item, uid_mapping) for item in obj]
        
        elif isinstance(obj, dict):
            # Handle nested structures - replace UIDs in BOTH keys and values
            new_dict = {}
            for key, value in obj.items():
                # Replace UID in key if it's a step UID
                new_key = uid_mapping.get(key, key) if isinstance(key, str) else key
                # Replace UIDs in value recursively
                new_value = self._replace_step_uids(value, uid_mapping)
                new_dict[new_key] = new_value
            return new_dict
        
        else:
            return obj

    # NOTE: _walk_and_replace, _clone_ref_with_mapping, and _replace_string_refs
    # have been replaced by the shared RefRemapper utility in core/ref/remapper.py
