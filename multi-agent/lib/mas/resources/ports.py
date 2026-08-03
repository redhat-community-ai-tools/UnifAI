"""
Ports (interfaces) for external dependencies of the resources domain.

Services and adapters depend on these ABCs rather than concrete
implementations, keeping the dependency arrows pointing inward.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class CredentialCleanupPort(Protocol):
    """Capability to delete stored credentials when no resource references them."""

    def delete_credential(self, user_id: str, server_identifier: str) -> None: ...
