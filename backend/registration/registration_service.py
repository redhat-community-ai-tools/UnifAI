from __future__ import annotations

from typing import Any, Dict, List

from registration.factory import RegistrationFactory
from shared.logger import logger
from shared.source_types import RegistrationResponse
from utils.storage.mongo.mongo_helpers import get_mongo_storage


class RegistrationService:
    """
    Synchronous registration service that creates registration flow instances
    and executes them.
    """

    def __init__(self) -> None:
        self.mongo_storage = get_mongo_storage()
        self.factory = RegistrationFactory(mongo_storage=self.mongo_storage)

    def register_sources(self, *, data_list: List[Dict[str, Any]], source_type: str, upload_by: str) -> Dict[str, Any]:
        """
        Register provided data sources synchronously and return a structured response.
        """
        logger.info(f"Starting synchronous registration for {len(data_list)} {source_type} sources by user {upload_by}")

        registered_sources: List[Dict[str, Any]] = []
        issues: List[Dict[str, Any]] = []

        for instance in data_list:
            registrar = self.factory.create(source_type=source_type, upload_by=upload_by, instance=instance)
            registered, issue = registrar.run_registration()
            if issue is not None:
                issues.append(issue)
                continue
            if registered is not None:
                registered_sources.append(registered)

        return RegistrationResponse(
            status="registration_complete",
            registered_sources=registered_sources,
            issues=issues,
        ).model_dump()


