from typing import List, Dict, Optional, Iterator
import logging
from global_utils.utils.logging_config import emit
from .models import Step

logger = logging.getLogger(__name__)


class GraphPlan:
    """
    Container for workflow steps. Pure data structure, no validation logic.

    Responsibilities:
      - Store and retrieve steps
      - Query graph structure (roots, leaves, dependencies)
      - Serialization for debugging
    """

    def __init__(self) -> None:
        self._steps: List[Step] = []
        self._index: Dict[str, Step] = {}

    @property
    def steps(self) -> List[Step]:
        """Ordered list of steps."""
        return list(self._steps)

    def add_step(self, step: Step) -> None:
        """Add a step to the plan."""
        if step.uid in self._index:
            raise ValueError(f"Step '{step.uid}' already exists in plan.")
        self._steps.append(step)
        self._index[step.uid] = step

    def get_step(self, uid: str) -> Optional[Step]:
        """Get step by uid."""
        return self._index.get(uid)

    def remove_step(self, uid: str) -> None:
        """Remove a step by uid."""
        step = self._index.pop(uid, None)
        if step:
            self._steps = [s for s in self._steps if s.uid != uid]

    def get_roots(self) -> List[Step]:
        """Return steps with no dependencies and are not branch targets."""
        # Collect all branch targets across all steps
        branch_targets = set()
        for step in self._steps:
            branch_targets.update(step.branches.values())

        # A root is a step with no 'after' dependencies AND not a branch target
        return [s for s in self._steps if not s.after and s.uid not in branch_targets]

    def get_leaves(self) -> List[Step]:
        """Return steps with no outgoing edges (true leaf nodes)."""
        steps_with_outgoing = set()
        
        for step in self._steps:
            # Check if this step has outgoing edges via 'after' dependencies
            # (i.e., if other steps depend on this step)
            for other in self._steps:
                if step.uid in other.after:
                    steps_with_outgoing.add(step.uid)
                    break
            
            # Check if this step has outgoing conditional branches
            if step.branches:
                steps_with_outgoing.add(step.uid)
        
        # Leaves are steps with NO outgoing edges
        return [s for s in self._steps if s.uid not in steps_with_outgoing]

    def to_dict(self) -> Dict:
        """Serialize for debugging/logging."""
        return {
            s.uid: {
                "type": s.type_key,
                "reads": list(s.total_reads()),
                "writes": list(s.writes),
                "after": s.after,
                "branches": s.branches
            }
            for s in self._steps
        }

    def __iter__(self) -> Iterator[Step]:
        """Make GraphPlan iterable."""
        return iter(self.steps)

    def __len__(self) -> int:
        """Number of steps."""
        return len(self._steps)

    def pretty_print(self) -> None:
        """
        Print out the plan as an ASCII tree, showing dependencies.
        If a node depends on multiple parents (e.g. agent_merger),
        it will be shown once, after all its parents.
        """
        roots = self.get_roots()
        visited = set()

        def _format_step(step, prefix, is_last):
            # Print the node
            bullet = "└── " if is_last else "├── "
            emit(logger, logging.DEBUG, "graph.plan_tree_line", line=f"{prefix}{bullet}{step.uid}")
            # Avoid re-visiting
            if step.uid in visited:
                return
            visited.add(step.uid)

            # Recurse into its children (single-parent edges only)
            child_prefix = prefix + ("    " if is_last else "│   ")
            children = [
                s for s in self.steps
                # only those whose .after is exactly [step.uid] or includes it among multiple parents
                if s.after and step.uid in s.after
            ]
            # But skip any multi-parent nodes here; we’ll handle them at the parent level
            single_parent_children = [c for c in children if not c.after or len(c.after) == 1]
            for i, child in enumerate(single_parent_children):
                _format_step(child, child_prefix, i == len(single_parent_children) - 1)

        for root in roots:
            emit(logger, logging.DEBUG, "graph.plan_tree_line", line=root.uid)
            visited.add(root.uid)

            # 1) print its single-parent children (agent_1, agent_2)
            direct = [
                s for s in self.steps
                if s.after and s.after == [root.uid]
            ]
            for i, child in enumerate(direct):
                _format_step(child, "", False)

            # 2) now find any merge nodes whose all parents are in `direct`
            direct_uids = {c.uid for c in direct}
            merges = [
                s for s in self.steps
                if s.after and len(s.after) > 1 and set(s.after) <= direct_uids
            ]
            if merges:
                # we assume just one merge for simplicity
                merge = merges[0]
                _format_step(merge, "", True)
