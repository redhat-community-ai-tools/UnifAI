"""Port: Python interpreter resolution."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PythonResolver(ABC):

    @abstractmethod
    def find_python(
        self,
        python_min: tuple[int, int],
        python_max: tuple[int, int],
        *,
        env_override: str | None = None,
    ) -> tuple[str, str]:
        """Find a suitable Python interpreter within the given version range.

        *env_override* is an explicit interpreter path/name (e.g. from
        ``UNIFAI_PYTHON``).  When provided, only that candidate is tried.

        Returns ``(resolved_path, minor_version_string)`` – e.g.
        ``("/usr/bin/python3.12", "3.12")``.  Raises ``RuntimeError``
        when no valid interpreter is found.
        """
