"""Registration domain models - value objects for source data."""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class BaseSourceData:
    """Base value object for source registration data."""
    source_name: str
    source_id: str
    pipeline_id: str
    form_data: Dict[str, Any]


@dataclass(frozen=True)
class DocumentSourceData(BaseSourceData):
    """Value object for document source data."""
    doc_path: str
    md5: str


@dataclass(frozen=True)
class SlackSourceData(BaseSourceData):
    """Value object for Slack source data."""
    pass
