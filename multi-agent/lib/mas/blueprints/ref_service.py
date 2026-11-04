from __future__ import annotations

import copy
from typing import Dict, List

from pydantic import BaseModel

from mas.blueprints.repository.repository import BlueprintRepository
from mas.core.ref import RefRemapper
from mas.core.ref.raw_blueprint_spec import (
    dedupe_blueprint_catalogue,
    extract_ref_ids_from_raw_spec,
    remove_resource_ref_from_catalogue,
    remove_resource_ref_from_nested_dict,
)


class BlueprintRefSummary(BaseModel):
    """Id and display name for a stored blueprint."""

    id: str
    name: str


class BlueprintRefService:
    """
    Manages resource-reference maintenance within stored blueprints.

    Operates on raw spec_dict (bypassing BlueprintDraft validation)
    to safely handle legacy blueprint shapes. Keeps the rid_refs
    index consistent after every mutation.
    """

    def __init__(self, repo: BlueprintRepository):
        self._repo = repo

    def list_usage(self, rid: str) -> List[str]:
        """Blueprint IDs whose catalogue entries reference rid."""
        return self._repo.list_direct_usage(rid)

    def get_summary(self, blueprint_id: str) -> BlueprintRefSummary:
        """Lightweight id and name for UI display."""
        bp_doc = self._repo.load(blueprint_id)
        return BlueprintRefSummary(
            id=blueprint_id,
            name=bp_doc.spec_dict.get("name", blueprint_id),
        )

    def remap_refs(self, blueprint_id: str, mapping: Dict[str, str]) -> None:
        """Replace old rids with new rids in a blueprint's spec."""
        bp_doc = self._repo.load(blueprint_id)
        spec = RefRemapper.remap(bp_doc.spec_dict, mapping)
        spec = dedupe_blueprint_catalogue(spec)
        self._save_spec(blueprint_id, spec)

    def strip_refs(self, blueprint_id: str, rid: str) -> None:
        """Remove all traces of rid from a blueprint's spec."""
        bp_doc = self._repo.load(blueprint_id)
        spec = remove_resource_ref_from_catalogue(bp_doc.spec_dict, rid)
        spec = remove_resource_ref_from_nested_dict(spec, rid)
        self._save_spec(blueprint_id, spec)

    def delete(self, blueprint_id: str) -> bool:
        """Delete a blueprint document."""
        return self._repo.delete(blueprint_id)

    def capture_spec(self, blueprint_id: str) -> tuple[dict, list[str]]:
        """Return a detached copy of a blueprint spec and its ``rid_refs``."""
        doc = self._repo.load(blueprint_id)
        return copy.deepcopy(doc.spec_dict), list(doc.rid_refs)

    def restore_spec(self, blueprint_id: str, spec_dict: dict, rid_refs: list[str]) -> None:
        """Write a previously captured spec and rid index back unchanged."""
        self._repo.update_raw(
            blueprint_id=blueprint_id,
            spec_dict=copy.deepcopy(spec_dict),
            rid_refs=list(rid_refs),
        )

    def _save_spec(self, blueprint_id: str, spec: dict) -> None:
        """Persist spec_dict and recompute rid_refs index."""
        rid_refs = list(extract_ref_ids_from_raw_spec(spec))
        self._repo.update_raw(
            blueprint_id=blueprint_id, spec_dict=spec, rid_refs=rid_refs
        )
