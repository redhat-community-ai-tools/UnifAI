from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Sandbox Exec tool."""
    TYPE = "sandbox_exec"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Sandbox Exec",
    description="Execute a shell command inside an OpenShell sandbox",
    tags=["tool", "sandbox", "exec", "openshell", "container"],
)
