"""
Runtime-enabled GraphPlan wrapper.

Composes a logical GraphPlan with runtime elements and element cards.
"""

from typing import List, Dict, Optional, Iterator, Any
from mas.session.domain.session_registry import SessionRegistry
from mas.session.collector import SessionConfigCollector
from mas.catalog.element_registry import ElementRegistry
from mas.catalog.card_service import ElementCardService
from mas.elements.common.card import ElementCard
from mas.core.enums import ResourceCategory
from mas.core.contracts import SupportsStepContext
from .graph_plan import GraphPlan
from .models import AdjacentNodes, Step, RTStep, StepContext
from .topology.finalizer_analyzer import FinalizerAnalyzer


class RTGraphPlan:
    """
    Runtime-enabled GraphPlan wrapper.

    Composes a logical GraphPlan and provides the same interface
    but with RTStep objects containing bound callables.
    """

    def __init__(
            self,
            logical_plan: GraphPlan,
            session_registry: SessionRegistry,
            element_registry: ElementRegistry
    ):
        self._logical_plan = logical_plan
        self._session = session_registry
        self._card_service = ElementCardService(element_registry)
        self._session_collector = SessionConfigCollector()
        self._cards: Dict[str, ElementCard] = {}
        self._rt_steps: Dict[str, RTStep] = {}

        self._build_all_cards()
        self._build_runtime_steps()

    @property
    def steps(self) -> List[RTStep]:
        """Get all runtime steps."""
        return list(self._rt_steps.values())

    def get_step(self, uid: str) -> Optional[RTStep]:
        """Get runtime step by uid."""
        return self._rt_steps.get(uid)

    def get_roots(self) -> List[RTStep]:
        """Get steps with no dependencies."""
        return [self._rt_steps[s.uid] for s in self._logical_plan.get_roots()]

    def get_leaves(self) -> List[RTStep]:
        """Get steps with no dependents."""
        return [self._rt_steps[s.uid] for s in self._logical_plan.get_leaves()]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for debugging (delegates to logical plan)."""
        return self._logical_plan.to_dict()

    def add_step(self, step: RTStep) -> None:
        """Add step (for interface compatibility if needed)."""
        raise NotImplementedError("RTGraphPlan is immutable after construction")

    def remove_step(self, uid: str) -> None:
        """Remove step (for interface compatibility if needed)."""
        raise NotImplementedError("RTGraphPlan is immutable after construction")

    def pretty_print(self) -> None:
        """Print plan structure (delegates to logical plan)."""
        self._logical_plan.pretty_print()

    def __iter__(self) -> Iterator[RTStep]:
        """Iterate over runtime steps."""
        return iter(self.steps)

    def __len__(self) -> int:
        """Number of steps."""
        return len(self._rt_steps)

    @property
    def session_registry(self) -> SessionRegistry:
        """Expose the session registry for external consumers (e.g., serializers)."""
        return self._session

    # ------------------------------------------------------------------ #
    #  Private Implementation
    # ------------------------------------------------------------------ #

    def _build_all_cards(self) -> None:
        """Build all element cards from session registry using SessionConfigCollector."""
        configs = self._session_collector.collect(self._session)
        self._cards = self._card_service.build_all_cards(configs)

    def _get_card(self, rid: str, step_uid: str, metadata: Any) -> ElementCard:
        """Get card for a node, adding step-specific metadata."""
        base_card = self._cards.get(rid)
        if base_card is None:
            return None

        return base_card.model_copy(update={"uid": step_uid, "metadata": metadata})

    def _build_runtime_steps(self) -> None:
        """Build all runtime steps from logical steps."""
        for logical_step in self._logical_plan.steps:
            rt_step = self._create_runtime_step(logical_step)
            self._rt_steps[logical_step.uid] = rt_step

    def _create_runtime_step(self, step: Step) -> RTStep:
        """Create a runtime step from a logical step."""
        adjacent_nodes_dict = {}

        for other_step in self._logical_plan.steps:
            if step.uid in other_step.after:
                card = self._get_card(other_step.rid, other_step.uid, other_step.meta)
                if card:
                    adjacent_nodes_dict[other_step.uid] = card

        branches: Dict[str, str] = step.branches or {}
        for outcome, next_uid in branches.items():
            tgt = self._logical_plan.get_step(next_uid)
            if tgt is not None:
                card = self._get_card(tgt.rid, tgt.uid, tgt.meta)
                if card:
                    adjacent_nodes_dict[next_uid] = card

        adjacent_nodes = AdjacentNodes.from_dict(adjacent_nodes_dict)

        analyzer = FinalizerAnalyzer(output_channel="output")
        adjacent_node_uids = list(adjacent_nodes_dict.keys())

        topology = analyzer.analyze_node_topology(
            plan=self._logical_plan,
            from_node_uid=step.uid,
            adjacent_node_uids=adjacent_node_uids
        )

        step_context = StepContext(
            uid=step.uid,
            metadata=step.meta,
            adjacent_nodes=adjacent_nodes,
            branches=branches,
            topology=topology,
        )

        node_func = self._session.get_instance(ResourceCategory.NODE, step.rid)
        if isinstance(node_func, SupportsStepContext):
            node_func.set_context(step_context)

        condition_func = None
        if step.condition:
            condition_func = self._session.get_instance(ResourceCategory.CONDITION, step.condition.rid)
            if isinstance(condition_func, SupportsStepContext):
                condition_func.set_context(step_context)

        return RTStep(
            step=step,
            func=node_func,
            exit_condition=condition_func,
        )
