"""Document Pipeline Handler - Source-specific pipeline operations for Documents."""
from typing import List, Dict, Any

from core.pipeline.domain.port import SourcePipelinePort, PipelineContext
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import VectorChunk
from core.data_sources.types.document.domain.processor import DocumentProcessor
from infrastructure.sources.document.connector import DocumentConnector
from infrastructure.sources.document.chunker import PDFChunkerStrategy
from shared.logger import logger

from global_utils.utils import cleanup_file


class DocumentPipelineHandler(SourcePipelinePort):
    """
    Handler for Document pipeline operations.
    
    Coordinates document-specific data flow through collection,
    processing, and embedding stages.
    
    This handler:
    - Collects document content (PDF, markdown, etc.)
    - Processes document text (cleans, normalizes)
    - Chunks content and generates embeddings
    - Cleans up temporary files after execution
    """
    
    def __init__(
        self,
        connector: DocumentConnector,
        processor: DocumentProcessor,
        chunker: PDFChunkerStrategy,
        embedder: EmbeddingGenerator,
    ):
        """
        Initialize the Document pipeline handler.
        
        Args:
            connector: Document connector for file processing
            processor: Document processor for text transformation
            chunker: PDF/Document chunker for content splitting
            embedder: Embedding generator for vector creation
        """
        self._connector = connector
        self._processor = processor
        self._chunker = chunker
        self._embedder = embedder
        self._cached_collected = None
    
    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "DOCUMENT"
    
    def collect(self, context: PipelineContext) -> Dict:
        """
        Collect document content.
        
        Args:
            context: Pipeline context with document path information
            
        Returns:
            Document data dictionary with content and metadata
        """
        logger.info(f"Collecting document: {context.metadata.get('doc_path')}")
        
        self._cached_collected = self._connector.process_document(
            document_path=context.metadata.get("doc_path"),
            upload_by=context.metadata.get("upload_by"),
        )
        return self._cached_collected
    
    def process(self, context: PipelineContext, raw_data: Dict) -> Dict:
        """
        Process document content.
        
        Args:
            context: Pipeline context
            raw_data: Document data from collect step
            
        Returns:
            Processed document dictionary
        """
        return self._processor.process(
            raw_data,
            clean_markdown=False,
            clean_text=False,
            remove_references=False,
            preserve_original=True,
        )
    
    def chunk_and_embed(self, context: PipelineContext, processed: Dict) -> List[VectorChunk]:
        """
        Chunk content and generate embeddings.
        
        Args:
            context: Pipeline context
            processed: Processed document data
            
        Returns:
            List of VectorChunk objects ready for storage
        """
        # Prepare document for embedding
        embedding_ready = self._processor.prepare_for_single_doc_embedding(processed)
        
        # Chunk the content
        chunks = self._chunker.chunk_content([embedding_ready])
        
        # Enrich with source metadata
        for idx, chunk in enumerate(chunks):
            chunk.setdefault("metadata", {}).update({
                "source_id": context.source_id,
                "source_type": self.source_type,
            })
        
        # Generate embeddings and convert to domain objects
        enriched_dicts = self._embedder.generate_embeddings(chunks)
        
        return [
            VectorChunk(
                text=d["text"],
                embedding=d["embedding"].tolist() if hasattr(d["embedding"], 'tolist') else d["embedding"],
                metadata=d.get("metadata", {})
            )
            for d in enriched_dicts
        ]
    
    def get_summary(self, context: PipelineContext, collected: Any) -> Dict:
        """
        Get execution summary for Document pipeline.
        
        Args:
            context: Pipeline context
            collected: Collected document data
            
        Returns:
            Summary dictionary with document-specific information
        """
        if self._cached_collected:
            return {
                "page_count": self._cached_collected.get("metadata", {}).get("page_count", 0),
                "full_text": self._cached_collected.get("text", ""),
                "file_size": self._cached_collected.get("metadata", {}).get("file_size", 0),
            }
        return {
            "page_count": 0,
            "full_text": "",
            "file_size": 0,
        }
    
    def cleanup(self, context: PipelineContext) -> bool:
        """
        Cleanup uploaded document file after pipeline execution.
        
        Args:
            context: Pipeline context with document path
        """
        doc_path = context.metadata.get("doc_path")
        if doc_path:
            return cleanup_file(doc_path, "after pipeline completion")
        return False
