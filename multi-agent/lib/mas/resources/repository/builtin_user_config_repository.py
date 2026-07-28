from abc import ABC, abstractmethod
from typing import List, Optional

from mas.resources.builtin_models import BuiltinUserConfig


class BuiltinUserConfigRepository(ABC):
    """Storage port for per-identity configuration overlays on built-in resources."""

    @abstractmethod
    def save(self, config: BuiltinUserConfig) -> str:
        """Insert or update a user config document (upsert on resource_id + identity_key)."""
        ...

    @abstractmethod
    def get(self, resource_id: str, identity_key: str) -> Optional[BuiltinUserConfig]:
        """Find the user config for a given resource + identity. Returns None if not found."""
        ...

    @abstractmethod
    def get_by_id(self, config_id: str) -> BuiltinUserConfig:
        """Retrieve a config by its ID. Raises KeyError if not found."""
        ...

    @abstractmethod
    def delete(self, resource_id: str, identity_key: str) -> None:
        """Delete a specific user config."""
        ...

    @abstractmethod
    def delete_all_for_resource(self, resource_id: str) -> int:
        """Delete all user configs for a resource. Returns count deleted."""
        ...

    @abstractmethod
    def find_by_identity(self, identity_key: str) -> List[BuiltinUserConfig]:
        """Return all user configs for a given identity across all resources."""
        ...
