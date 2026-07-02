from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseSandbox(ABC):
    """Abstract sandbox execution environment.

    All sandbox backends (OpenShell, KATA, Firecracker, ...) must implement
    this interface. Sessions, connections, and other backend-specific concepts
    are hidden as implementation details.
    """

    @property
    @abstractmethod
    def sandbox_name(self) -> Optional[str]:
        """Current sandbox identifier, or None if not yet created."""
        ...

    @property
    @abstractmethod
    def workdir(self) -> str:
        """Default working directory inside the sandbox."""
        ...

    @abstractmethod
    def bind_context(self, *, session_id: str = "", agent_id: str = "") -> None:
        """Late-bind execution context for deterministic sandbox naming."""
        ...

    @abstractmethod
    def exec(
        self,
        cmd: List[str],
        *,
        stdin: Optional[bytes] = None,
        workdir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> Any:
        """Execute a command inside the sandbox."""
        ...

    @abstractmethod
    def exec_python(
        self,
        function: Any,
        *,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        workdir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 300,
    ) -> Any:
        """Serialize a Python callable via cloudpickle and run it in the sandbox."""
        ...

    @abstractmethod
    def add_allowed_endpoints(self, urls: List[str]) -> None:
        """Register URLs that the sandbox needs to reach for network policy."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Delete sandbox and release resources."""
        ...
