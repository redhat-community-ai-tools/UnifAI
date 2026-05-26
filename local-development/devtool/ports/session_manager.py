"""Port: session manager for launching services in tmux or foreground."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from devtool.domain.models import WindowLayout


class SessionManager(ABC):

    @abstractmethod
    def launch(
        self,
        session_name: str,
        layout: list[WindowLayout],
        commands: dict[str, str],
        log_dir: Path,
    ) -> None:
        """Launch the given services.

        *layout* is a list of window definitions, each containing a name
        and a list of services.  *commands* maps service name → full shell
        command string.  The adapter decides how to arrange them (tmux
        windows/panes, foreground exec, etc.).
        """

    @abstractmethod
    def attach(self, session_name: str) -> None:
        """Attach to an existing session (tmux-specific, no-op for foreground)."""

    @abstractmethod
    def kill_session(self, session_name: str) -> None:
        """Destroy the session and all its processes."""

    @abstractmethod
    def is_running(self, session_name: str) -> bool:
        """Return True if the session exists and has running processes."""

    @abstractmethod
    def graceful_stop(self, session_name: str, timeout: int = 10) -> None:
        """Send interrupt to all processes and wait for them to exit.

        After *timeout* seconds, forcefully kill the session.
        """

    @abstractmethod
    def pane_contents(self, session_name: str) -> dict[str, str]:
        """Return ``{pane_ref: captured_text}`` for every pane in the session.

        *pane_ref* is ``"<window>.<pane>"`` (e.g. ``"0.2"``).
        Returns an empty dict when the session is not running.
        """

    @abstractmethod
    def select_pane(self, session_name: str, pane_ref: str) -> None:
        """Focus the given pane (e.g. switch to its window and select it).

        *pane_ref* is ``"<window_index>.<pane_index>"``.
        No-op for session types that don't support panes.
        """

    @abstractmethod
    def restart_service(self, session_name: str, service_name: str) -> bool:
        """Send restart signal to the process running *service_name*.

        Returns True if a matching process was found and signalled.
        """
