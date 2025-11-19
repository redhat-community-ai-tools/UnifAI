from __future__ import annotations

from typing import Any, Dict

from config.constants import DataSource

from .base import RegistrationBase
from .document import DocumentRegistration
from .slack import SlackRegistration


class RegistrationFactory:
    """Factory to create registration flows based on data source type."""

    def __init__(self, mongo_storage: Any) -> None:
        self.mongo_storage = mongo_storage

    def create(self, source_type: str, upload_by: str, instance: Dict[str, Any]) -> RegistrationBase:
        normalized = (source_type or "").strip().lower()

        if normalized == DataSource.SLACK.value:
            return SlackRegistration(self.mongo_storage, upload_by, instance)

        if normalized == DataSource.DOCUMENT.value:
            return DocumentRegistration(self.mongo_storage, upload_by, instance)

        raise ValueError(f"Unsupported source type: {source_type}")


