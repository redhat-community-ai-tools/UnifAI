from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Tuple
from functools import cached_property
from dataclasses import dataclass
from backend.registration.base import BaseSourceData
from backend.registration.base import RegistrationBase
from config.app_config import AppConfig
from config.constants import DataSource
from shared.source_types import DocumentMetadata, DocumentTypeData
from utils.file_hash import compute_file_md5
from validator.validator import Validator, DocValidators

app_config = AppConfig.get_instance()
upload_folder = app_config.upload_folder

@dataclass(frozen=True)
class DocumentSourceData(BaseSourceData):
    doc_path: str
    md5: str
    
class DocumentRegistration(RegistrationBase):
    """Registration flow for Document sources."""
    DATA_SOURCE_TYPE = DataSource.DOCUMENT.upper_name

    def __init__(self, mongo_storage: Any, upload_by: str, instance: Dict[str, Any]) -> None:
        super().__init__(mongo_storage, upload_by, instance)
        self.upload_folder = upload_folder
        self._validator = Validator(DocValidators().create_validators())

    @cached_property
    def source_data(self) -> DocumentSourceData:
        name = self.instance.get("source_name", "")
        path = os.path.join(self.upload_folder, name)
        md5 = compute_file_md5(path)
        sid = str(uuid.uuid4())
        pid = f"{DataSource.DOCUMENT.value}_{sid}"
        form_data = self.instance.get("metadata", {})
        return DocumentSourceData(
            source_name=name,
            source_id=sid,
            pipeline_id=pid,
            doc_path=path,
            md5=md5,
            form_data=form_data,
        )

    def run_validator(self) -> Tuple[bool, Dict[str, Any] | None]:
        validation_args = {
            "doc_path": self.source_data.doc_path,
            "source_name": self.source_data.source_name,
            "md5": self.source_data.md5
        }
        is_valid, issue = self._validator.validate(**validation_args)

        if not is_valid:
            issue_key = (issue or {}).get("issue_key", "ValidationError")
            message = (issue or {}).get("message", "Validation error")
            validator_name = (issue or {}).get("validator_name", "Validator")
            return False, {
                "doc_name": self.source_data.source_name,
                "issue_type": issue_key,
                "message": message,
                "validator": validator_name,
            }

        return True, None

    def _build_metadata(self) -> DocumentMetadata:
        return DocumentMetadata(
            doc_id=self.source_data.source_id,
            doc_name=self.source_data.source_name,
            doc_path=self.source_data.doc_path,
            upload_by=self.upload_by,
        )

    def _build_type_data(self) -> Dict[str, Any]:
        doc_type_data = DocumentTypeData(
            file_type=self.source_data.source_name.rsplit(".", 1)[-1].lower(),
            doc_path=self.source_data.doc_path,
            page_count=0,
            full_text="",
            file_size=0,
            md5=self.source_data.md5,
            **self.source_data.form_data,
        )
        return doc_type_data.model_dump()
