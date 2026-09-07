"""
Document Connector - unified document processing adapter.

This connector uses a DocumentConverterPort for the actual conversion,
allowing seamless switching between local and remote implementations.
"""

import os
import logging
from typing import List, Optional

from core.connector.domain.base import DataConnector
from core.health.domain.port import HealthCheckable
from core.data_sources.types.document.domain.document_converter import (
    DocumentConverterPort,
    DocumentConversionError,
)
from core.data_sources.types.document.domain.processed_document import ProcessedDocument
from infrastructure.sources.document.config import DocConfigManager

logger = logging.getLogger("rag_pipeline")


class DocumentConnector(DataConnector, HealthCheckable):
    """
    Unified document connector using port-based architecture.

    The actual document conversion is delegated to a DocumentConverterPort,
    which can be either LocalDoclingAdapter or RemoteDoclingAdapter.
    """

    def __init__(
        self,
        converter: DocumentConverterPort,
        config_manager: Optional[DocConfigManager] = None,
    ):
        if config_manager is None:
            config_manager = DocConfigManager()

        super().__init__(config_manager)

        self._converter = converter

        logger.info(
            f"DocumentConnector initialized with {type(converter).__name__}"
        )

    @property
    def is_remote(self) -> bool:
        """True if the underlying converter calls an external service."""
        return self._converter.is_remote

    def test_connection(self) -> bool:
        """Test if document processing is available."""
        return self._converter.test_connection()

    def process_document(
        self,
        document_path: str,
        upload_by: str = "default",
    ) -> ProcessedDocument:
        """
        Process a document file and extract text and metadata.

        Args:
            document_path: Path to the document file
            upload_by: User who uploaded the document

        Returns:
            ProcessedDocument containing extracted text, markdown, and metadata
        """
        logger.info(f"Processing document: {document_path}")

        result = self._converter.convert_file(document_path)

        metadata = {}
        if self._config_manager.get_config_value("include_metadata"):
            metadata = dict(result.metadata)
            metadata["upload_by"] = upload_by
            if os.path.exists(document_path):
                file_size_mb = os.path.getsize(document_path) / (1024 * 1024)
                metadata["file_size"] = f"{file_size_mb:.2f} MB"

        logger.info(f"Document processed: {document_path}")
        return ProcessedDocument(
            text=result.text,
            markdown=result.markdown,
            path=document_path,
            filename=os.path.basename(document_path),
            metadata=metadata,
        )

    def process_documents(self, document_paths: List[str]) -> List[ProcessedDocument]:
        """Process multiple documents."""
        logger.info(f"Processing batch of {len(document_paths)} documents")

        results = []
        failed_count = 0

        for doc_path in document_paths:
            try:
                results.append(self.process_document(doc_path))
            except DocumentConversionError as e:
                logger.error(f"Failed to process {doc_path}: {e}")
                failed_count += 1

        logger.info(
            f"Batch complete. Processed {len(results)}/{len(document_paths)}. "
            f"Failed: {failed_count}"
        )
        return results

    def process_document_url(
        self,
        document_url: str,
        upload_by: str = "default",
    ) -> ProcessedDocument:
        """Process a document from a URL."""
        logger.info(f"Processing document URL: {document_url}")

        result = self._converter.convert_url(document_url)

        metadata = {}
        if self._config_manager.get_config_value("include_metadata"):
            metadata = dict(result.metadata)
            metadata["upload_by"] = upload_by

        logger.info(f"Document URL processed: {document_url}")
        return ProcessedDocument(
            text=result.text,
            markdown=result.markdown,
            path=document_url,
            filename="",
            metadata=metadata,
        )
