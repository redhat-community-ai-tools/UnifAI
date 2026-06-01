"""Port: Node.js interpreter resolution."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NodeResolver(ABC):

    @abstractmethod
    def check_node(self, min_major: int) -> tuple[str, str]:
        """Verify that Node.js is installed and meets the minimum version.

        Returns ``(resolved_path, version_string)`` — e.g.
        ``("/usr/bin/node", "22.11.0")``.  Raises ``RuntimeError``
        when Node.js is missing or too old.
        """
