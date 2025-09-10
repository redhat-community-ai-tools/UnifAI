from typing import List, Dict, Optional, Any
import hashlib
from datetime import datetime
from config.constants import PipelineStatus
from data_sources.docs.doc_connector import DocumentConnector, DuplicateDocumentError
from data_sources.docs.document_processor import DocumentProcessor
from data_sources.docs.pdf_chunker_strategy import PDFChunkerStrategy
from shared.source_types import DocumentMetadata
from config.constants import DataSource
from pipeline.pipeline import Pipeline
from utils.embedding.embedding_generator import EmbeddingGenerator
from utils.monitor.pipeline_monitor import PipelineMonitor
from utils.storage.vector_storage import VectorStorage
from threading import Thread
from data_sources.docs.docs_validator import DocumentValidator

class DocumentPipeline(Pipeline):
    SOURCE_TYPE = DataSource.DOCUMENT.upper_name
    def __init__(
        self,
        collector: DocumentConnector,
        validator: DocumentValidator,
        processor: DocumentProcessor,
        chunker: PDFChunkerStrategy,
        embedder: EmbeddingGenerator,
        storage: VectorStorage,
        monitor: PipelineMonitor,
        metadata: DocumentMetadata
    ):
        self.collector = collector
        self.validator = validator
        self.doc_processor = processor
        self.doc_chunker = chunker
        self.embedder = embedder
        self._cached_collected = None
        self._document_metadata: DocumentMetadata = metadata
        
        super().__init__(
            collector=collector,
            processor=processor,
            chunker=chunker,
            embedder=embedder,
            storage=storage,
            monitor=monitor,
            metadata=metadata
        )

    def get_source_id(self) -> str:
        return self._document_metadata.doc_id

    def get_source_name(self) -> str:
        return self._document_metadata.doc_name or f"document_{self._document_metadata.doc_id}"

    def summary(self) -> Dict:
        if self._cached_collected:
            md = self._cached_collected.get("metadata", {})
            return {
                "page_count": md.get("page_count", 0),
                "full_text": self._cached_collected.get("text", ""),
                "file_size": md.get("file_size", 0),
                "content_md5": md.get("content_md5", ""),
            }
        else:
            return {
                "page_count": 0,
                "full_text": "",
                "file_size": 0,
                "content_md5": "",
            }

    def collect_data(self) -> Dict:
        doc_path = self._document_metadata.doc_path
        if not doc_path:
            raise ValueError("Document path is required for document collection")
        upload_by = self._document_metadata.upload_by or "default"
        self._cached_collected = self.collector.process_document(
            document_path=doc_path,
            upload_by=upload_by
        )
        return self._cached_collected or {}


    def process_data(self, data: Dict) -> Dict:
        # Validate there are no duplicates before processing
        self.validator.validate(
            collected=data or {},
            pipeline_id=self.get_pipeline_id(),
            source_name=self.get_source_name(),
            uploader=str(self._document_metadata.upload_by or "default"),
        )

        return self.doc_processor.process(
            data,
            clean_markdown=False,
            clean_text=False,
            remove_references=False,
            preserve_original=True
        )

    def chunk_and_embed(self, processed: Dict) -> List[Dict]:
        embedding_ready_doc = self.doc_processor.prepare_for_single_doc_embedding(processed)
        chunks = self.doc_chunker.chunk_content([embedding_ready_doc])

        for idx, chunk in enumerate(chunks):
            md = chunk.setdefault("metadata", {})
            md.update({
                "source_id": self._document_metadata.doc_id,
                "source_type": DataSource.DOCUMENT.upper_name,
            })

        return self.embedder.generate_embeddings(chunks)

