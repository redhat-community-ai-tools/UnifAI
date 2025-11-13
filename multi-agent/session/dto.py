from dataclasses import dataclass, asdict
from typing import Any, Dict, Mapping


@dataclass(slots=True)
class ChatHistoryItem:
    session_id: str
    metadata: Dict[str, Any]
    started_at: str
    blueprint_id: str
    blueprint_exists: bool = True

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any], blueprint_exists: bool = True) -> "ChatHistoryItem":
        rc = doc.get("run_context", {})
        return cls(
            session_id=rc.get("run_id"),
            metadata=doc.get("metadata", {}),
            started_at=rc.get("started_at"),
            blueprint_id=doc.get("blueprint_id", ""),
            blueprint_exists=blueprint_exists
        )

    # optional helper
    def asdict(self) -> Dict[str, Any]:
        return asdict(self)
