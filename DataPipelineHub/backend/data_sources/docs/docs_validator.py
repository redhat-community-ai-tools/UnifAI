from typing import Dict, Any
from shared.logger import logger
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from config.constants import SourceType
from data_sources.docs.doc_connector import DuplicateDocumentError
from utils.documents import compute_file_md5


class DocumentValidator:
    """Validate collected document source data (e.g. duplication checks).

    Responsibilities:
    - Ensure content MD5 exists (compute from text if missing)
    - Check for existing sources with same MD5 and DONE pipeline status
    - If duplicate found: perform duplicate handling via storage and raise DuplicateDocumentError
    """

    def validate(self, collected: Dict[str, Any], pipeline_id: str, source_name: str, uploader: str) -> None:
        if not collected:
            return

        metadata = collected.setdefault("metadata", {})
        content_md5 = metadata.get("content_md5")

        # Ensure MD5 present; compute from text if needed
        if not content_md5:
            try:
                text = collected.get("text", "")
                content_md5 = compute_file_md5(text)
                if not content_md5:
                    return
                metadata["content_md5"] = content_md5
            except Exception as e:
                logger.warning(f"Failed to compute MD5 for document analysis: {e}")
                content_md5 = None
                
        try:
            storage = get_mongo_storage()
            original_doc = storage.find_duplicate_source_by_md5(content_md5, SourceType.DOCUMENT.value.upper())
            if original_doc:
                # Perform duplicate handling in storage, then raise to abort pipeline
                storage.handle_document_duplicate(
                    original_doc=original_doc,
                    duplicate_pipeline_id=pipeline_id,
                    duplicate_source_name=source_name,
                    uploader=uploader or "default",
                )
                raise DuplicateDocumentError(original_doc=original_doc)
        except DuplicateDocumentError:
            raise
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return


