from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Tuple
from functools import cached_property
from dataclasses import dataclass
from registration.base import BaseSourceData
from registration.base import RegistrationBase
from global_utils.utils import secure_filename, compute_file_md5, cleanup_file
from config.app_config import AppConfig
from config.constants import DataSource
from shared.source_types import DocumentMetadata, DocumentTypeData
from validator.validator import Validator, DocValidators

app_config = AppConfig.get_instance()
upload_folder = app_config.upload_folder

@dataclass(frozen=True)
class DocumentSourceData(BaseSourceData):
    doc_path: str
    md5: str
    
class DocumentRegistration(RegistrationBase):
    """
    Registration flow for Document sources.
    
    Supports skip_validation flag:
    - When False (default): Full validation (extension, size, name, MD5)
      Used for external API calls that didn't pre-validate
    - When True: Only MD5 duplicate validation
      Used for UI uploads that pre-validated via /docs/validate endpoint
    """
    DATA_SOURCE_TYPE = DataSource.DOCUMENT.upper_name

    def __init__(
        self, 
        mongo_storage: Any, 
        upload_by: str, 
        instance: Dict[str, Any],
        skip_validation: bool = False
    ) -> None:
        super().__init__(mongo_storage, upload_by, instance, skip_validation)
        self.upload_folder = upload_folder
        # Create validators based on skip_validation flag
        self._validator = Validator(DocValidators().create_validators(skip_validation))

    @cached_property
    def source_data(self) -> DocumentSourceData:
        # Get the original name for display purposes
        original_name = self.instance.get("source_name", "")
        # Use secure_filename to get the actual filename which matches what upload_docs() does when saving the file
        secure_name = secure_filename(original_name)
        path = os.path.join(self.upload_folder, secure_name)
        md5 = compute_file_md5(path)
        sid = str(uuid.uuid4())
        pid = f"{DataSource.DOCUMENT.value}_{sid}"
        form_data = self.instance.get("metadata", {})
        return DocumentSourceData(
            source_name=original_name,
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
            "md5": self.source_data.md5,
            "upload_by": self.upload_by,
        }
        is_valid, issue = self._validator.validate(**validation_args)

        if not is_valid:
            # Clean up the uploaded file since it failed validation
            cleanup_file(self.source_data.doc_path, "after validation failure")
            
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
