"""
Auth-layer storage ports — protocol-agnostic persistence contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import StoredCredential, ClientConfig


class CredentialStore(ABC):
    """Persist and retrieve :class:`StoredCredential` objects."""

    @abstractmethod
    def upsert(self, credential: StoredCredential) -> None: ...

    @abstractmethod
    def find_by_server(
        self, user_id: str, server_identifier: str, scheme_type: str = "",
    ) -> Optional[StoredCredential]: ...

    @abstractmethod
    def delete(self, user_id: str, server_identifier: str) -> None: ...

    @abstractmethod
    def update_status(self, user_id: str, server_identifier: str, status: str) -> None: ...


class ServerConfigStore(ABC):
    """Persist and retrieve :class:`ClientConfig` objects."""

    @abstractmethod
    def find_by_server(self, user_id: str, server_identifier: str) -> Optional[ClientConfig]: ...

    @abstractmethod
    def save(self, user_id: str, config: ClientConfig) -> None: ...
