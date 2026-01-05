from typing import List, Dict
from data_sources.docs.doc_connector import DocumentConnector
from data_sources.docs.document_processor import DocumentProcessor
from data_sources.docs.pdf_chunker_strategy import PDFChunkerStrategy
from shared.source_types import DocumentMetadata
from config.constants import DataSource
from pipeline.pipeline import Pipeline
from utils.embedding.embedding_generator import EmbeddingGenerator
from utils.monitor.pipeline_monitor import PipelineMonitor
from utils.storage.vector_storage import VectorStorage
from global_utils.utils import cleanup_file

class DocumentPipeline(Pipeline):
    SOURCE_TYPE = DataSource.DOCUMENT.upper_name
    def __init__(
        self,
        collector: DocumentConnector,
        processor: DocumentProcessor,
        chunker: PDFChunkerStrategy,
        embedder: EmbeddingGenerator,
        storage: VectorStorage,
        monitor: PipelineMonitor,
        metadata: DocumentMetadata
    ):
        self.collector = collector
        self.doc_processor = processor
        self.doc_chunker = chunker
        self.embedder = embedder
        self._cached_collected = None
        
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
        return self.metadata.doc_id

    def get_source_name(self) -> str:
        return self.metadata.doc_name or f"document_{self.metadata.doc_id}"

    def summary(self) -> Dict:
        if self._cached_collected:
            return {
                "page_count": self._cached_collected.get("metadata", {}).get("page_count", 0),
                "full_text": self._cached_collected.get("text", ""),
                "file_size": self._cached_collected.get("metadata", {}).get("file_size", 0),
            }
        else:
            return {
                "page_count": 0,
                "full_text": "",
                "file_size": 0,
            }

    def collect_data(self) -> Dict:
        self._cached_collected = self.collector.process_document(
            document_path=self.metadata.doc_path,
            upload_by=self.metadata.upload_by
        )
        return self._cached_collected

    def process_data(self, data: Dict) -> Dict:
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
                "source_id": self.metadata.doc_id,
                "source_type": DataSource.DOCUMENT.upper_name,
            })

        return self.embedder.generate_embeddings(chunks)

    def cleanup(self) -> bool:
        """
        Cleanup uploaded document file after pipeline execution.
        
        Returns:
            True if cleanup was performed, False otherwise.
        """
        doc_path = getattr(self.metadata, 'doc_path', None)
        if doc_path:
            return cleanup_file(doc_path, "after pipeline completion")
        return False
