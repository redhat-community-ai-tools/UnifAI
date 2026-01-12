from dataclasses import dataclass
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class RuntimeElement:
    """Complete runtime element: instance + spec + resource_spec."""
    instance: Any
    spec: Any
    resource_spec: Any  # ResourceSpec with user-defined name, config, rid, type
    
    @property
    def config(self) -> Any:
        """Get config from resource_spec."""
        return self.resource_spec.config if self.resource_spec else None


class SessionMeta(BaseModel):
    """Session metadata with Pydantic validation."""
    title: str | None = None
    tags: Dict[str, str] = Field(default_factory=dict)
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMeta":
        return cls(**data)
