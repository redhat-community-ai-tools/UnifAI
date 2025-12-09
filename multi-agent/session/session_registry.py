from typing import Any, Dict
from core.enums import ResourceCategory
from session.models import RuntimeElement


class SessionRegistry:
    """
    IOC container for session-scoped resources (LLMs, Tools, Providers, …).

    *One* dict keyed by ResourceCategory, then by user-chosen name.
    """

    def __init__(self) -> None:
        self._store: Dict[ResourceCategory, Dict[str, RuntimeElement]] = {
            cat: {} for cat in ResourceCategory
        }
        self._frozen = False  # to optionally lock after build

    # ─────────────── public, generic API ────────────────
    def register(self, category: ResourceCategory, rid: str,
                 instance: Any, spec: Any, resource_spec: Any) -> None:
        """Register complete runtime element (instance + spec + resource_spec)."""
        self._assert_not_frozen()
        self._store[category][rid] = RuntimeElement(
            instance=instance,
            spec=spec,
            resource_spec=resource_spec
        )

    def get(self, category: ResourceCategory, rid: str) -> RuntimeElement:
        """Get complete runtime element (instance + config + spec)."""
        return self._store[category][rid]

    def get_instance(self, category: ResourceCategory, rid: str) -> Any:
        """Get instance only."""
        return self._store[category][rid].instance

    def get_config(self, category: ResourceCategory, rid: str) -> Any:
        """Get config only."""
        return self._store[category][rid].config

    def get_spec(self, category: ResourceCategory, rid: str) -> Any:
        """Get spec only."""
        return self._store[category][rid].spec

    def get_runtime_element(self, category: ResourceCategory, rid: str) -> RuntimeElement:
        """Get complete runtime element (backwards compatibility)."""
        return self._store[category][rid]

    def all_of(self, category: ResourceCategory) -> Dict[str, Any]:
        """Read-only view of instances in a category (useful in debugging)."""
        return {rid: runtime_element.instance
                for rid, runtime_element in self._store[category].items()}

    # optional safety: freeze after build
    def freeze(self) -> None:
        self._frozen = True

    # internal helper
    def _assert_not_frozen(self):
        if self._frozen:
            raise RuntimeError("SessionRegistry is frozen—no new registrations allowed.")
