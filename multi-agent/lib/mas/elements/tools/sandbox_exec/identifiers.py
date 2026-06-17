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
    description=(
        "Execute commands in isolated sandboxes containers on a "
        "user-provisioned OpenShell gateway VM"
    ),
    tags=["tool", "sandbox", "exec", "openshell", "container", "execution"],
)
