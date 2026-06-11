from abc import ABC, abstractmethod


class SessionStorageCleaner(ABC):
    """Outbound port for session working-directory lifecycle.

    Implementations handle the actual infrastructure (local filesystem,
    S3, etc.).  Domain code calls cleanup() without knowing the backend.
    """

    @abstractmethod
    def cleanup(self, session_id: str) -> None:
        """Remove all working-directory storage for a session.

        Best-effort — implementations should log failures but not raise.
        """
        ...
