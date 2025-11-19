from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple
from dataclasses import dataclass
from shared.logger import logger
from shared.source_types import RegisteredSource

@dataclass(frozen=True)
class BaseSourceData:
    source_name: str
    source_id: str
    pipeline_id: str
    form_data: Dict[str, Any]

class RegistrationBase(ABC):
    """
    Abstract base for source registration flows.

    Implementations should orchestrate validation and persistence while preserving
    the existing behavior for their specific source type.
    """

    def __init__(self, mongo_storage: Any, upload_by: str, instance: Dict[str, Any]) -> None:
        self.mongo_storage = mongo_storage
        self.upload_by = upload_by
        self.instance = instance
        
    def run_registration(self) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """
        Orchestrate the single-item registration flow:
        1) validate the instance
        2) register (persist) if valid
        Returns (registered_source_dict, issue_dict)
        """
        is_valid, issue = self.run_validator()
        if not is_valid:
            return None, issue
        return self.register()

    @property
    @abstractmethod
    def source_data(self) -> BaseSourceData:
        """Aggregated, immutable source data object (id, name, pipeline_id, form_data, etc.)."""
        raise NotImplementedError

    def register(self) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """
        Register a single instance. Returns (registered_source_dict, issue_dict).
        If registration is successful, issue_dict should be None. If validation fails,
        registered_source_dict should be None and issue_dict should contain structured info.
        """
        metadata = self._build_metadata()
        type_data = self._build_type_data()
        self._persist_common(
            source_id=self.source_data.source_id,
            source_name=self.source_data.source_name,
            source_type_upper=self.DATA_SOURCE_TYPE,
            pipeline_id=self.source_data.pipeline_id,
            type_data=type_data,
        )
        registered_source = self._build_registered_source_common(
            pipeline_id=self.source_data.pipeline_id,
            metadata=metadata,
            source_type_upper=self.DATA_SOURCE_TYPE,
            type_data=type_data,
        )
        self._log_registered_common(
            source_type_upper=self.DATA_SOURCE_TYPE,
            source_name=self.source_data.source_name,
            pipeline_id=self.source_data.pipeline_id,
            form_data=self.source_data.form_data,
        )
        return registered_source, None

    @abstractmethod
    def run_validator(self) -> Tuple[bool, Dict[str, Any] | None]:
        """Run source-specific validation for a single instance and return (is_valid, issue)."""
        raise NotImplementedError

    def _persist_common(
        self,
        *,
        source_id: str,
        source_name: str,
        source_type_upper: str,
        pipeline_id: str,
        type_data: Dict[str, Any],
    ) -> None:
        self.mongo_storage.upsert_source_summary(
            source_id=source_id,
            source_name=source_name,
            source_type=source_type_upper,
            upload_by=self.upload_by,
            pipeline_id=pipeline_id,
            type_data=type_data,
        )

    def _build_registered_source_common(
        self,
        *,
        pipeline_id: str,
        metadata: Any,
        source_type_upper: str,
        type_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        registered_source = RegisteredSource(
            pipeline_id=pipeline_id,
            metadata=metadata.__dict__,
            source_type=source_type_upper,
            upload_by=self.upload_by,
            type_data=type_data,
        )
        return registered_source.model_dump()

    def _log_registered_common(
        self,
        *,
        source_type_upper: str,
        source_name: str,
        pipeline_id: str,
        form_data: Dict[str, Any],
    ) -> None:
        metadata_info = f" with form data: {form_data}" if form_data else ""
        logger.info(
            f"Registered {source_type_upper} source: {source_name} with pipeline_id: {pipeline_id}{metadata_info}"
        )


