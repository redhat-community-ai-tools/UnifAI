"""mas.catalog.spec_discoverer
~~~~~~~~~~~~~~~~~~~~~~~~
Utility responsible solely for **discovering** element `Spec` classes.
It performs two tasks:

1. Import every *elements/<category>/<element>/spec* package so that the
   Python interpreter actually executes the module that defines the
   `BaseElementSpec` subclass.
2. Walk the `BaseElementSpec` subclass tree to collect every concrete
   implementation, skipping abstract helper classes.

The class is intentionally *stateless* except for its configuration so
that the discovery strategy can be swapped or tested in isolation.

Rationale & Design Goals
-----------------------
• Keep `BaseElementSpec` a passive data holder – no self-registration.
• Keep `ElementRegistry` focused on storage & query – no IO or walking.
• Allow alternative discovery strategies (entry-points, zipfiles, …)
  by replacing this class or subclassing it.
"""

import importlib
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple, Type


from mas.elements.common.base_element_spec import BaseElementSpec

logger = logging.getLogger(__name__)


class SpecDiscoverer:
    """Filesystem (+ optional entry-point) based discovery of Spec classes."""

    # Entry-point group constant – can be overridden via constructor
    ELEMENTS_DIR = "elements"
    ELEMENTS_MODULE = "mas.elements"
    SPEC_DIR = "spec"

    def __init__(
            self,
            elements_root: str | os.PathLike | None = None,
    ) -> None:
        """Create a discoverer.

        Parameters
        ----------
        elements_root
            Root directory that contains the *elements/* package.
            If *None*, defaults to *cwd/elements*.
        include_entrypoints
            If *True*, discover external plug-ins registered via
            *importlib.metadata* entry-points under *entrypoint_group*.
        """
        if elements_root:
            self._root = Path(elements_root)
        else:
            self._root = Path(__file__).resolve().parent.parent / self.ELEMENTS_DIR

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def discover(self) -> List[Type[BaseElementSpec]]:
        """Import packages and return every concrete `BaseElementSpec` subclass."""
        self._import_filesystem_packages()

        return self._collect_specs()

    # ------------------------------------------------------------------
    #  Step 1: Import packages so classes are defined
    # ------------------------------------------------------------------
    def _import_filesystem_packages(self) -> None:
        """Walk the *elements/* directory and import *spec* sub-packages."""

        source_root = self._root.parent.parent
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))

        root = self._root
        if not root.exists():
            # Nothing to import; warn the user but do not crash.
            logger.warning("catalog.discover_dir_not_found", extra={"root": str(root)})
            return

        for category_dir in root.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("__"):
                continue

            for element_dir in category_dir.iterdir():
                if not element_dir.is_dir():
                    continue

                spec_pkg = element_dir / self.SPEC_DIR
                if not (spec_pkg / "__init__.py").exists():
                    continue  # Not an element with a spec package

                module_name = f"{self.ELEMENTS_MODULE}.{category_dir.name}.{element_dir.name}.{self.SPEC_DIR}"
                self._safe_import(module_name)

    # ------------------------------------------------------------------
    #  Step 2: Collect concrete subclasses
    # ------------------------------------------------------------------
    def _collect_specs(self) -> List[Type[BaseElementSpec]]:
        """Return all *concrete* `BaseElementSpec` subclasses (duplicates pruned)."""
        collected: List[Type[BaseElementSpec]] = []
        seen: Set[Tuple[str, str]] = set()  # (category, type_key) tuples

        def walk(cls: Type[BaseElementSpec]):  # recursive DFS
            for sub in cls.__subclasses__():
                if inspect.isabstract(sub):
                    walk(sub)
                    continue

                # Ensure we only add each (category, type_key) once
                key = (sub.category.value if hasattr(sub.category, "value") else str(sub.category),
                       # type: ignore[attr-defined]
                       sub.type_key)
                if key not in seen:
                    seen.add(key)
                    collected.append(sub)

                walk(sub)  # recurse further – there might be deeper levels

        walk(BaseElementSpec)

        # Deterministic order: category, then type_key
        collected.sort(key=lambda s: (str(s.category), s.type_key))
        return collected

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_import(module_name: str) -> None:
        """Import *module_name* once, ignoring failures with a log message."""
        if module_name in sys.modules:
            return

        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover – never crash discovery
            # TODO when adding logging print the traceback
            logger.warning("catalog.discover_import_failed", extra={"module": module_name, "error": str(exc)})
