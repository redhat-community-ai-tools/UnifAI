from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from mas.resources.models import Resource
from mas.blueprints.ref_service import BlueprintRefService
from mas.resources.registry import ResourcesRegistry


@dataclass(frozen=True)
class DeletionContext:
    """
    Immutable context passed to delete strategies.

    Built once by the service before dispatch.
    """

    resource: Resource
    replacement_rid: Optional[str]
    blueprint_ids: List[str]
    registry: ResourcesRegistry
    bp_refs: BlueprintRefService
