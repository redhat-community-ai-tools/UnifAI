"""mas.actions.registry.action_discoverer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Utility responsible solely for **discovering** action classes.
It performs two tasks:

1. Import every *actions/<category>/<action>* module so that the
   Python interpreter actually executes the module that defines the
   `BaseAction` subclass.
2. Walk the `BaseAction` subclass tree to collect every concrete
   implementation, skipping abstract helper classes.

The class is intentionally *stateless* except for its configuration so
that the discovery strategy can be swapped or tested in isolation.

Rationale & Design Goals
-----------------------
• Keep `BaseAction` a passive data holder – no self-registration.
• Keep `ActionRegistry` focused on storage & query – no IO or walking.
• Allow alternative discovery strategies (entry-points, zipfiles, …)
  by replacing this class or subclassing it.
"""

import importlib
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import List, Set, Type


from mas.actions.common.base_action import BaseAction

logger = logging.getLogger(__name__)


class ActionDiscoverer:
    """Filesystem-based discovery of Action classes."""

    # Package constants – can be overridden via constructor
    ACTIONS_DIR = "actions"
    ACTIONS_MODULE = "mas.actions"

    def __init__(
            self,
            actions_root: str | os.PathLike | None = None,
    ) -> None:
        """Create a discoverer.

        Parameters
        ----------
        actions_root
            Root directory that contains the *actions/* package.
            If *None*, defaults to *cwd/actions*.
        """
        if actions_root:
            self._root = Path(actions_root)
        else:
            self._root = Path(__file__).resolve().parent.parent.parent / self.ACTIONS_DIR

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def discover(self) -> List[Type[BaseAction]]:
        """Import packages and return every concrete `BaseAction` subclass."""
        self._import_filesystem_packages()
        return self._collect_actions()

    # ------------------------------------------------------------------
    #  Step 1: Import packages so classes are defined
    # ------------------------------------------------------------------
    def _import_filesystem_packages(self) -> None:
        """Walk the *actions/* directory and import action modules."""

        source_root = self._root.parent.parent
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))

        root = self._root
        if not root.exists():
            # Nothing to import; warn the user but do not crash.
            logger.warning("catalog.discover_dir_not_found", extra={"root": str(root)})
            return

        # Import all action packages in the actions directory tree
        self._import_action_packages_recursively(root, self.ACTIONS_MODULE)

    def _import_action_packages_recursively(self, directory: Path, package_prefix: str) -> None:
        """Recursively import action packages (directories with __init__.py)."""
        for item in directory.iterdir():
            if item.name.startswith("__"):
                continue  # Skip __pycache__, __init__.py, etc.

            if item.is_dir():
                # Only process subdirectories that have __init__.py (proper packages)
                init_file = item / "__init__.py"
                if init_file.exists():
                    # Import the package - this will load anything imported in __init__.py
                    package_name = f"{package_prefix}.{item.name}"
                    self._safe_import(package_name)
                    
                    # Recursively process subdirectories
                    self._import_action_packages_recursively(item, package_name)
                else:
                    logger.warning("catalog.discover_skip_directory", extra={"directory": str(item)})

    # ------------------------------------------------------------------
    #  Step 2: Collect concrete subclasses
    # ------------------------------------------------------------------
    def _collect_actions(self) -> List[Type[BaseAction]]:
        """Return all *concrete* `BaseAction` subclasses (duplicates pruned)."""
        collected: List[Type[BaseAction]] = []
        seen: Set[str] = set()  # UIDs to prevent duplicates

        def walk(cls: Type[BaseAction]):  # recursive DFS
            for sub in cls.__subclasses__():
                if inspect.isabstract(sub):
                    walk(sub)
                    continue

                # Only add concrete actions with UIDs
                if hasattr(sub, 'uid') and sub.uid:
                    if sub.uid not in seen:
                        seen.add(sub.uid)
                        collected.append(sub)
                    else:
                        logger.warning("catalog.discover_duplicate_uid", extra={"uid": sub.uid, "module": sub.__module__})

                walk(sub)  # recurse further – there might be deeper levels

        walk(BaseAction)

        # Deterministic order: by UID
        collected.sort(key=lambda a: a.uid)
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
