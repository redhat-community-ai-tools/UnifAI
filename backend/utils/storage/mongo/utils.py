from datetime import datetime
from bson import ObjectId
from typing import Any, Dict

def make_json_safe(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectIds and datetimes into strings for JSON serialization."""
    def convert(val: Any) -> Any:
        if isinstance(val, ObjectId):
            return str(val)
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, dict):
            return make_json_safe(val)
        if isinstance(val, list):
            return [convert(i) for i in val]
        return val

    return {k: convert(v) for k, v in doc.items()} 