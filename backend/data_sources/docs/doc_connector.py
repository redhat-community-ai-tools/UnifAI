import os
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from shared.logger import logger
from utils.data_connector import DataConnector
from .doc_config_manager import DocConfigManager
from .pdf_chunker_strategy import DoclingProcessingError
from .docling_service_client import DoclingServiceClient

class DocumentConnector(DataConnector):
    """
    Document connector for processing PDF and other document formats.
    
    Handles extraction of text and metadata from documents using the external docling service.
    """
    
    def __init__(self, config_manager: Optional[DocConfigManager] = None):
        """
        Initialize the document connector.
        
        Args:
            config_manager: Configuration manager for document processing
        """
        if config_manager is None:
            config_manager = DocConfigManager()
            
        super().__init__(config_manager)
        
        # Initialize the docling service client
        # Timeout is read from AppConfig.docling_service_timeout by default
        # DocConfigManager can override if timeout_seconds is explicitly set
        config_timeout = self._config_manager.get_config_value("timeout_seconds")
        self._service_client = DoclingServiceClient(timeout=config_timeout)
        
        # Store conversion results for metadata extraction
        self._conversion_results: Dict[str, Dict[str, Any]] = {}
        logger.info("DocumentConnector initialized with docling service client")
    
    def authenticate(self) -> bool:
        """
        No authentication required for local document processing.
        
        Returns:
            True as no authentication is needed
        """
        logger.info("Document connector does not require authentication")
        return True
    
    def test_connection(self) -> bool:
        """
        Test if document processing is available and working.
        
        Returns:
            True if document processing capabilities are available
        """
        return self._service_client.test_connection()
    
    def process_document(self, document_path: str, upload_by: str = "default") -> Optional[Dict[str, Any]]:
        """
        Process a document file and extract text and metadata.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            Dictionary containing extracted text and metadata, or None if processing failed
        """
        # Validate the file exists
        if not os.path.exists(document_path):
            logger.error(f"Document not found: {document_path}")
            raise DoclingProcessingError(f"Document not found: {document_path}")
            
        # Validate file extension
        _, file_extension = os.path.splitext(document_path)
        supported_extensions = self._config_manager.get_config_value("supported_extensions")
        
        if file_extension.lower() not in supported_extensions:
            logger.error(f"Unsupported file extension: {file_extension}. Supported types: {supported_extensions}")
            raise DoclingProcessingError(f"Unsupported file extension: {file_extension}. Supported types: {supported_extensions}")

        # Check file size
        file_size_mb = os.path.getsize(document_path) / (1024 * 1024)
        max_size_mb = self._config_manager.get_config_value("max_file_size_mb")

        if file_size_mb > max_size_mb:
            logger.error(f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)")
            raise DoclingProcessingError(f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)")
            
        try:
            logger.info(f"Processing document: {document_path}")
            
            # Process the document with docling service
            result = self._service_client.convert_file(document_path, to_formats=["md", "text"])
            
            # Store the conversion result for future reference
            self._conversion_results[document_path] = result
            
            # Extract text and markdown from service response
            text_content = result.get("text", "")
            markdown_content = result.get("markdown", "")
            
            # Validate that we extracted content
            if not text_content or not text_content.strip():
                # If no text, try to use markdown as fallback
                if markdown_content and markdown_content.strip():
                    text_content = markdown_content
                else:
                    logger.error(f"Docling service failed to extract text content from document: {document_path}")
                    raise DoclingProcessingError(
                        f"Docling service was unable to process the provided document "
                        f"'{os.path.basename(document_path)}'. Failed to extract text content from the document."
                    )
       
            document_data = {
                "text": text_content,
                "markdown": markdown_content if markdown_content else text_content,
                "path": document_path,
                "filename": os.path.basename(document_path),
            }
            
            # Add metadata if requested
            if self._config_manager.get_config_value("include_metadata"):
                document_data["metadata"] = self._extract_metadata(
                    result, upload_by, file_size_mb, text_content
                )
                
            logger.info(f"Document processed successfully: {document_path}")
            return document_data
            
        except DoclingProcessingError:
            raise
        except Exception as e:
            logger.error(f"Error processing document {document_path}: {str(e)}")
            raise DoclingProcessingError(str(e))
    
    def process_documents(self, document_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple documents.
        
        Args:
            document_paths: List of paths to document files
            
        Returns:
            List of processed document data
        """
        logger.info(f"Processing batch of {len(document_paths)} documents")
        results = []
        
        for doc_path in document_paths:
            result = self.process_document(doc_path)
            if result:
                results.append(result)
                
        logger.info(f"Batch processing complete. Processed {len(results)} out of {len(document_paths)} documents")
        return results
    
    def process_document_url(self, document_url: str) -> Optional[Dict[str, Any]]:
        """
        Process a document from a URL.
        
        Args:
            document_url: URL of the document
            
        Returns:
            Dictionary containing extracted text and metadata, or None if processing failed
        """
        try:
            logger.info(f"Processing document from URL: {document_url}")
            
            # Process the document with docling service
            result = self._service_client.convert_url(document_url, to_formats=["md", "text"])
            
            # Store the conversion result for future reference
            self._conversion_results[document_url] = result
            
            # Extract text and markdown from service response
            text_content = result.get("text", "")
            markdown_content = result.get("markdown", "")
            
            # Validate that we extracted meaningful content
            if not text_content or not text_content.strip():
                # If no text, try to use markdown as fallback
                if markdown_content and markdown_content.strip():
                    text_content = markdown_content
                else:
                    logger.error(f"Docling service failed to extract text content from document URL: {document_url}")
                    raise DoclingProcessingError(
                        f"Docling service was unable to process the provided document from URL "
                        f"'{document_url}'. Failed to extract text content from the document."
                    )
                        
            document_data = {
                "text": text_content,
                "markdown": markdown_content if markdown_content else text_content,
                "url": document_url,
            }
            
            # Add metadata if requested
            if self._config_manager.get_config_value("include_metadata"):
                document_data["metadata"] = self._extract_metadata(
                    result, upload_by="default", file_size=0, text_content=text_content
                )
                
            logger.info(f"Document from URL processed successfully: {document_url}")
            return document_data
            
        except DoclingProcessingError:
            raise
        except Exception as e:
            logger.error(f"Error processing document from URL {document_url}: {str(e)}")
            raise DoclingProcessingError(str(e))
    
    def _extract_metadata(
        self, 
        conversion_result: Dict[str, Any], 
        upload_by: str = "default", 
        file_size: float = 0,
        text_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata from a conversion result.
        
        Args:
            conversion_result: The document conversion result from the service
            upload_by: User who uploaded the document
            file_size: File size in MB
            text_content: Text content for statistics (if not in conversion_result)
            
        Returns:
            Dictionary containing document metadata
        """
        metadata = {}
        
        try:
            # Extract metadata from service response if available
            if "metadata" in conversion_result and isinstance(conversion_result["metadata"], dict):
                metadata.update(conversion_result["metadata"])

            # Extract title from metadata or use default
            metadata["title"] = metadata.get("title", "Untitled")

            # Extract uploader
            metadata["upload_by"] = upload_by
            
            # Extract file size
            metadata["file_size"] = f"{file_size:.2f} MB" if file_size > 0 else "Unknown size"
                
            # Extract content statistics
            text = text_content or conversion_result.get("text", "")
            if text:
                metadata["character_count"] = len(text)
                metadata["word_count"] = len(text.split())
            else:
                metadata["character_count"] = 0
                metadata["word_count"] = 0
            
            # Extract page count from metadata if available, otherwise estimate
            if "page_count" not in metadata:
                # Estimate page count based on text length (rough estimate: ~2000 chars per page)
                if text:
                    estimated_pages = max(1, len(text) // 2000)
                    metadata["page_count"] = estimated_pages
                else:
                    metadata["page_count"] = 1
            
            # Extract table and image counts from metadata if available
            if "table_count" not in metadata:
                metadata["table_count"] = 0
            if "image_count" not in metadata:
                metadata["image_count"] = 0
                
        except Exception as e:
            logger.warning(f"Error extracting metadata: {str(e)}")
            
        return metadata
    
    def get_document_structure(self, document_path: str) -> Optional[Dict[str, Any]]:
        """
        Get the hierarchical structure of a document.
        
        Args:
            document_path: Path to the document
            
        Returns:
            Dictionary representing the document structure, or None if not available
        """
        if document_path not in self._conversion_results:
            logger.warning(f"Document not processed yet: {document_path}")
            return None
            
        try:
            result = self._conversion_results[document_path]
            structure = {
                "title": result.get("metadata", {}).get("title", "Untitled"),
                "sections": []
            }
            
            # Extract sections from markdown if available
            # This is a simplified version - the service may not provide detailed structure
            markdown = result.get("markdown", "")
            if markdown:
                # Try to extract headers from markdown
                header_pattern = r"^(#{1,6})\s+(.*)$"
                for line in markdown.split("\n"):
                    match = re.match(header_pattern, line)
                    if match:
                        level = len(match.group(1))
                        title = match.group(2).strip()
                        structure["sections"].append({
                            "title": title,
                            "level": level,
                            "text": ""
                        })
            
            return structure
            
        except Exception as e:
            logger.error(f"Error extracting document structure: {str(e)}")
            return None