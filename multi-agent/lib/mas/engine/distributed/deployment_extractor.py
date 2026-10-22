"""
Node deployment extractor for distributed execution.

Extracts mini-blueprints and StepContext from RTGraphPlan so that a
remote worker can rebuild and execute a single node without the full
blueprint or live graph.
"""
from typing import Any, Dict, Optional, Set, Tuple

from mas.core.enums import ResourceCategory
from mas.core.ref import RefWalker
from mas.graph.models.step_context import StepContext
from mas.session.domain.session_registry import SessionRegistry
from mas.graph.models.workflow import RTStep


class NodeDeploymentExtractor:
    """
    Responsible for preparing deployment payloads (mini-blueprints,
    step contexts) from runtime plan data.

    Separates deployment concerns from graph planning (SRP).
    """

    def __init__(self, session_registry: SessionRegistry) -> None:
        self._session = session_registry

    def serialize_node_blueprint(self, step: RTStep) -> Dict[str, Any]:
        """
        Return a serialized mini BlueprintSpec containing ONLY the
        resources this node needs (its LLM, providers, tools, etc.).
        """
        from mas.blueprints.models.blueprint import BlueprintSpec, StepDef
        from mas.core.ref.models import NodeRef

        node_elem = self._session.get(ResourceCategory.NODE, step.rid)
        node_spec = node_elem.resource_spec

        llms, providers, tools, retrievers, sandboxes = [], [], [], [], []
        for category, spec in self._collect_dependencies(node_spec):
            if category == ResourceCategory.LLM:
                llms.append(spec)
            elif category == ResourceCategory.PROVIDER:
                providers.append(spec)
            elif category == ResourceCategory.TOOL:
                tools.append(spec)
            elif category == ResourceCategory.RETRIEVER:
                retrievers.append(spec)
            elif category == ResourceCategory.SANDBOX:
                sandboxes.append(spec)

        mini_bp = BlueprintSpec(
            providers=providers,
            llms=llms,
            tools=tools,
            retrievers=retrievers,
            sandboxes=sandboxes,
            nodes=[node_spec],
            conditions=[],
            plan=[StepDef(uid=step.uid, node=NodeRef(node_spec.rid.root))],
            name="mini",
            description="",
        )
        return mini_bp.model_dump(mode="json")

    def serialize_condition_blueprint(self, condition_rid: str) -> Dict[str, Any]:
        """
        Return a serialized mini BlueprintSpec for a condition.
        Conditions are typically lightweight (no LLM, no tools).
        """
        from mas.blueprints.models.blueprint import BlueprintSpec

        cond_elem = self._session.get(ResourceCategory.CONDITION, condition_rid)
        cond_spec = cond_elem.resource_spec

        mini_bp = BlueprintSpec(
            providers=[],
            llms=[],
            tools=[],
            retrievers=[],
            nodes=[],
            conditions=[cond_spec],
            plan=[],
            name="mini",
            description="",
        )
        return mini_bp.model_dump(mode="json")

    def get_step_context(self, step: RTStep) -> Optional[StepContext]:
        """
        Return the StepContext for this node, or None if absent.

        Built from the FULL graph topology (adjacent nodes, finalizer
        distances, etc.) at compile time.
        """
        return step.func._ctx

    def _collect_dependencies(self, node_spec: Any) -> list:
        """Resources the node needs, directly or through other resources.

        A reference is a ``Ref`` field of a typed config: it is either
        ``$ref:<id>`` (stored resource) or a plain ``<id>`` (resource defined
        inline in the blueprint). Both are keys of the session registry, so
        both are collected; ids absent from the registry (e.g. a node ref)
        are skipped. Dependencies are followed transitively (a tool may need
        a provider).
        """
        found: list = []
        seen: Set[str] = set()
        pending = self._config_rids(node_spec.config)
        while pending:
            rid = pending.pop()
            if rid in seen:
                continue
            seen.add(rid)
            hit = self._find_resource_spec(rid)
            if hit is None:
                continue
            found.append(hit)
            pending |= self._config_rids(hit[1].config)
        return found

    @staticmethod
    def _config_rids(config: Any) -> Set[str]:
        rids = set(RefWalker.all_rids(config))
        # Also catch "$ref:" strings held by untyped fields (dicts of free-form values).
        rids |= _collect_refs(config.model_dump(mode="json"))
        return rids

    def _find_resource_spec(self, rid: str) -> Optional[Tuple[ResourceCategory, Any]]:
        """Look up a rid across all resource categories."""
        for category in ResourceCategory:
            try:
                elem = self._session.get(category, rid)
                return category, elem.resource_spec
            except (KeyError, IndexError):
                continue
        return None


def _collect_refs(obj: Any) -> Set[str]:
    """Recursively collect all $ref: rids from a serialized config."""
    refs: Set[str] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            refs.update(_collect_refs(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            refs.update(_collect_refs(item))
    elif isinstance(obj, str) and obj.startswith("$ref:"):
        refs.add(obj[5:])
    return refs
