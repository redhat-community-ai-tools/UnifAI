"""
Builds a SessionRegistry from a BlueprintSpec by orchestrating one
CategoryBuilder per resource category.

Key features
------------
* **Data-driven** – Build order is derived from `depends_on` declared on each
  CategoryBuilder subclass.  No hard-coded lists beyond registration.
* **Validated** – Unknown dependencies and cyclic graphs raise ValueError
  before any expensive objects are constructed.
* **SOLID** – The class depends only on the CategoryBuilder abstraction and
  SessionRegistry protocol; adding a new category means writing one new
  builder and importing it here.
"""

from collections import deque
from typing import Dict, List, Optional, Type
from mas.session.domain.session_registry import SessionRegistry
from mas.blueprints.models.blueprint import BlueprintSpec
from mas.core.enums import ResourceCategory
from mas.core.element_deps import ElementBuildContext

# concrete builders
from .category_builders.provider_builder import ProviderBuilder
from .category_builders.llm_builder import LLMBuilder
from .category_builders.retriever_builder import RetrieverBuilder
from .category_builders.condition_builder import ConditionBuilder
from .category_builders.tool_builder import ToolBuilder
from .category_builders.sandbox_builder import SandboxBuilder
from .category_builders.node_builder import NodeBuilder
from .category_builders.category_builder import CategoryBuilder


class SessionElementBuilder:
    """
    Orchestrates CategoryBuilders → returns a fully-populated SessionRegistry.
    """

    # Register all category builders once.  Order does *not* matter here;
    # topological sort from depends_on determines build order.
    _BUILDER_CLASSES: List[Type[CategoryBuilder]] = [
        ProviderBuilder,
        LLMBuilder,
        RetrieverBuilder,
        ConditionBuilder,
        ToolBuilder,
        SandboxBuilder,
        NodeBuilder
    ]

    # --------------------------------------------------------------------- #
    # Public API                                                            #
    # --------------------------------------------------------------------- #
    def __init__(self, element_registry):
        """
        Parameters
        ----------
        element_registry : ElementRegistry
            The plugin registry that knows every factory/schema pair.
            It is forwarded to each CategoryBuilder.
        """
        self._builders: Dict[ResourceCategory, CategoryBuilder] = {
            cls.category: cls(element_registry) for cls in self._BUILDER_CLASSES
        }
        # raises early on unknown deps / cycles
        self._ordered_builders: List[CategoryBuilder] = self._topological_order()

    # -- main entry ------------------------------------------------------------
    def build(
        self,
        blueprint: BlueprintSpec,
        deps: Optional[ElementBuildContext] = None,
    ) -> SessionRegistry:
        """Return a fully populated SessionRegistry.

        Cross-cutting runtime concerns are forwarded via the typed
        ``ElementBuildContext`` bag to each CategoryBuilder.
        """
        registry = SessionRegistry()

        for builder in self._ordered_builders:
            builder.build(blueprint, registry, deps=deps)

        registry.freeze()
        return registry

    # --------------------------------------------------------------------- #
    # Internal helpers                                                      #
    # --------------------------------------------------------------------- #
    def _topological_order(self) -> List[CategoryBuilder]:
        """
        Kahn’s algorithm topological sort.

        Raises
        ------
        ValueError
            • if any builder lists an unknown dependency
            • if a cyclic dependency is found
        """
        # Build adjacency map: category -> deps
        graph: Dict[ResourceCategory, set[ResourceCategory]] = {
            cat: set(b.depends_on) for cat, b in self._builders.items()
        }

        # --- validation: unknown deps -----------------------------------
        unknown = {d for deps in graph.values() for d in deps} - graph.keys()
        if unknown:
            cats = ", ".join(item.value for item in sorted(unknown))
            raise ValueError(f"Unknown builder dependency(ies): {cats}")

        # --- Kahn -------------------------------------------------------
        queue = deque([cat for cat, deps in graph.items() if not deps])
        ordered: List[CategoryBuilder] = []

        while queue:
            cat = queue.popleft()
            ordered.append(self._builders[cat])

            # remove edges
            for tgt in list(graph):
                if cat in graph[tgt]:
                    graph[tgt].discard(cat)
                    if not graph[tgt]:
                        queue.append(tgt)
            graph.pop(cat, None)

        # --- cycle detection -------------------------------------------
        if graph:  # any remaining nodes ⇒ cycle
            cycle = " → ".join(cat.value for cat in graph)
            raise ValueError(f"Cyclic builder dependencies detected: {cycle}")

        return ordered
