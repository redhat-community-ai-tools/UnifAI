from typing import Any, Dict, Mapping
from pydantic import BaseModel


class SessionListItem(BaseModel):
    session_id: str
    metadata: Dict[str, Any]
    started_at: str
    last_active_at: str = ""
    blueprint_id: str
    blueprint_exists: bool = True

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any], blueprint_exists: bool = True, public_usage_scope: bool = False, blueprint_metadata: Dict[str, Any] = None) -> "SessionListItem":
        rc = doc.get("run_context", {})
        return cls(
            session_id=doc.get("run_id", "") or rc.get("run_id", ""),
            metadata={
                **(blueprint_metadata or {}),
                **doc.get("metadata", {}),
                "public_usage_scope": public_usage_scope,
            },
            started_at=rc.get("started_at") or "",
            last_active_at=rc.get("last_active_at") or "",
            blueprint_id=doc.get("blueprint_id", ""),
            blueprint_exists=blueprint_exists
        )
