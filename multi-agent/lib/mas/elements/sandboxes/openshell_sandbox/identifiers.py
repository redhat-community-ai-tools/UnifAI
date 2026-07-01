from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    TYPE = "openshell_sandbox"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="OpenShell Sandbox",
    description="Execute commands inside an OpenShell sandbox via gRPC",
    tags=["sandbox", "openshell", "container", "execution"],
)
