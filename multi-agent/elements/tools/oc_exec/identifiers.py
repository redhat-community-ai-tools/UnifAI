from enum import Enum
from dataclasses import dataclass
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the OpenShift OC Exec tool."""
    TYPE = "oc_exec"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="OpenShift Command (OC) Exec",
    description="Execute oc commands on an OpenShift cluster",
    tags=["tool", "openshift", "oc", "kubernetes", "cluster", "exec"],
)
