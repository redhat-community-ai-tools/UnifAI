"""PDF chunking strategy implementation."""
from typing import Dict, List, Any
from core.vector.domain.chunker import ContentChunker
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from shared.logger import logger


class DoclingProcessingError(Exception):
    """Raised when docling fails to extract meaningful content from documents"""
    pass


class PDFChunkerStrategy(ContentChunker):
    """
    Implementation of ContentChunker for PDFs using langchain's RecursiveCharacterTextSplitter.
    
    This strategy intelligently chunks PDF content while preserving natural text boundaries
    and maintaining relationships between adjacent chunks.
    """
    
    def __init__(self, max_tokens_per_chunk: int = 500, overlap_tokens: int = 50):
        """
        Initialize the PDF chunker strategy.
        
        Args:
            max_tokens_per_chunk: Maximum number of tokens allowed in a single chunk
            overlap_tokens: Number of tokens to overlap between adjacent chunks
        """
        super().__init__(max_tokens_per_chunk, overlap_tokens)
        try:
            # Initialize tokenizer for token counting
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Using OpenAI's tokenizer
            logger.info("Initialized tiktoken tokenizer with cl100k_base encoding")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken: {e}. Using fallback token estimation.")
            self.tokenizer = None
            
        # Convert token sizes to approximate character counts (rough estimate)
        # Assuming average of 4 characters per token for English text
        chars_per_token = 4
        self.chunk_size = max_tokens_per_chunk * chars_per_token
        self.chunk_overlap = overlap_tokens * chars_per_token
        
        logger.info(f"Initialized PDFChunkerStrategy with chunk_size={self.chunk_size} chars and "
                   f"chunk_overlap={self.chunk_overlap} chars")
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.
        
        Args:
            text: Text to analyze
            
        Returns:
            Estimated token count
        """
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback estimation: approximately 4 characters per token for English
            return len(text) // 4
    
    def chunk_content(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Split PDF content into logical chunks while preserving natural boundaries.
        
        Args:
            documents: List of document objects with content and metadata
            
        Returns:
            List of chunks with content and metadata
        """
        logger.info(f"Starting to chunk {len(documents)} PDF documents")
        self._chunks = []
        
        for doc in documents:
            logger.info(f"Starting chunking procedure for: {doc.get('filename', 'Unknown')}")
            
            content = doc.get('content', '')
            if not content:
                logger.warning(f"Empty content for document {doc.get('filename', 'Unknown')}")
                continue
                
            # Create a text splitter that respects natural boundaries
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]  # Order matters: prefer splitting at paragraphs, then sentences
            )
            
            logger.info(f"Created RecursiveCharacterTextSplitter with chunk_size={self.chunk_size}, "
                       f"chunk_overlap={self.chunk_overlap}")
            
            # Split the text
            logger.info(f"Splitting content of {doc.get('filename', 'Unknown')}")
            
            raw_chunks = text_splitter.split_text(content)
            
            # Process chunks and add metadata
            doc_chunks = []
            for i, chunk_text in enumerate(raw_chunks):
                # Estimate token count for this chunk
                token_count = self.estimate_token_count(chunk_text)
                
                # Create chunk with metadata
                chunk = {
                    "id": f"{doc.get('id', 'unknown')}_chunk_{i}",
                    "text": chunk_text,
                    "metadata": {
                        **doc.get('metadata', {}),  # Include original document metadata
                        "chunk_index": i,
                        "total_chunks": len(raw_chunks),
                        "token_count": token_count,
                        "document_id": doc.get('id', 'unknown'),
                        "filename": doc.get('filename', 'unknown'),
                        # Add adjacent chunk references
                        "prev_chunk_id": f"{doc.get('id', 'unknown')}_chunk_{i-1}" if i > 0 else None,
                        "next_chunk_id": f"{doc.get('id', 'unknown')}_chunk_{i+1}" if i < len(raw_chunks) - 1 else None
                    }
                }
                
                doc_chunks.append(chunk)
            
            self._chunks.extend(doc_chunks)
        
        logger.info(f"Completed chunking with {len(self._chunks)} total chunks generated")

        return self._chunks
