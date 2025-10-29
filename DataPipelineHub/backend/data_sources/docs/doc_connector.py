import os
import requests
from typing import Dict, List, Any, Optional
from pathlib import Path
from shared.logger import logger
from utils.data_connector import DataConnector
from .doc_config_manager import DocConfigManager
from .pdf_chunker_strategy import DoclingProcessingError
from config.app_config import AppConfig

class DocumentConnector(DataConnector):
    """
    Document connector for processing PDF and other document formats.
    
    Handles extraction of text and metadata from documents using docling.
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
        
        # Initialize docling endpoint configuration
        self._app_config = AppConfig()

        # Try to get docling service URL from environment variables (set by Kubernetes)
        # Priority: K8s service discovery > external address > default localhost
        docling_ip = os.environ.get('DOCLING_IP')
        docling_port = os.environ.get('DOCLING_PORT')
        docling_ext_addr = os.environ.get('DOCLING_EXT_ADDR')

        if docling_ip and docling_port:
            # Use Kubernetes service discovery
            self._docling_base_url = f"http://{docling_ip}:{docling_port}"
        elif docling_ext_addr and docling_port:
            # Use external address from load balancer
            self._docling_base_url = f"http://{docling_ext_addr}:{docling_port}"
        else:
            # Fallback to configured URL (for local development)
            self._docling_base_url = self._app_config.docling_endpoint_url

        self._docling_api_version = self._app_config.docling_api_version
        self._docling_timeout = self._app_config.docling_timeout
        
        # Storage for conversion results
        self._conversion_results: Dict[str, Dict[str, Any]] = {}
        logger.info(f"DocumentConnector initialized with endpoint: {self._docling_base_url}")
    
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
        Test if docling endpoint is available and working.
        
        Returns:
            True if docling endpoint is accessible
        """
        try:
            # Test endpoint health
            health_url = f"{self._docling_base_url}/health"
            response = requests.get(health_url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Docling endpoint health check failed: {str(e)}")
            return False
    
    def process_document(self, document_path: str, upload_by: str = "default") -> Optional[Dict[str, Any]]:
        """
        Process a document file and extract text and metadata.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            Dictionary containing extracted text and metadata, or None if processing failed
        """
        logger.info(f"Starting document processing: {document_path}")
        
        # Validate the file exists
        if not os.path.exists(document_path):
            logger.error(f"Document not found: {document_path}")
            return None
        
        logger.info(f"File exists, size: {os.path.getsize(document_path)} bytes")
            
        # Validate file extension
        _, file_extension = os.path.splitext(document_path)
        supported_extensions = self._config_manager.get_config_value("supported_extensions")
        logger.info(f"File extension: {file_extension}, supported: {supported_extensions}")
        
        if file_extension.lower() not in supported_extensions:
            logger.error(f"Unsupported file extension: {file_extension}. Supported types: {supported_extensions}")
            return None

        # Check file size
        file_size_mb = os.path.getsize(document_path) / (1024 * 1024)
        max_size_mb = self._config_manager.get_config_value("max_file_size_mb")
        logger.info(f"File size: {file_size_mb:.2f} MB, max allowed: {max_size_mb} MB")

        if file_size_mb > max_size_mb:
            logger.error(f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)")
            return None
            
        try:
            logger.info(f"Processing document via docling endpoint: {self._docling_base_url}")
            
            # Process the document with docling endpoint
            result = self._convert_document_via_endpoint(document_path)
            logger.info(f"Docling endpoint returned result with keys: {list(result.keys())}")
            
            # Store the conversion result for future reference
            self._conversion_results[document_path] = result
            
            # Extract text and metadata from the docling chunking response
            # Docling chunking API returns chunks, we need to reconstruct the full text
            text_content = self._extract_text_from_chunks(result)
            markdown_content = self._extract_markdown_from_chunks(result)
            logger.info(f"Extracted text length: {len(text_content)}, markdown length: {len(markdown_content)}")
            
            # Validate that docling extracted content
            if not text_content or not text_content.strip():
                logger.warning(f"Docling endpoint processed successfully but extracted no text content from document: {document_path}")
                logger.info(f"This might be an image-based PDF requiring OCR, or the service may need different configuration")
                # Instead of failing completely, let's create a minimal placeholder
                text_content = f"[PDF processed but no text content extracted from {os.path.basename(document_path)}]"
                markdown_content = f"# {os.path.basename(document_path)}\n\n[Content extraction failed - may require OCR]"
       
            document_data = {
                "text": text_content,
                "markdown": markdown_content,
                "path": document_path,
                "filename": os.path.basename(document_path),
            }
            
            # Add metadata if requested
            if self._config_manager.get_config_value("include_metadata"):
                document_data["metadata"] = self._extract_metadata_from_response(result, upload_by, file_size_mb)
                
            logger.info(f"Document processed successfully via endpoint: {document_path}")
            return document_data
            
        except DoclingProcessingError:
            logger.error(f"DoclingProcessingError for {document_path}")
            raise
        except Exception as e:
            logger.error(f"Error processing document {document_path}: {str(e)}", exc_info=True)
            return None
    
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
    
    # URL processing removed - not used in production pipeline
    # Only file processing (process_document) is used by docs_pipeline.py
    
    def _convert_document_via_endpoint(self, document_path: str) -> Dict[str, Any]:
        """
        Convert a document file using the docling endpoint.
        
        Args:
            document_path: Path to the document file
            
        Returns:
            Dictionary containing conversion result
        """
        # Try the convert/file endpoint (based on Helm test pattern)
        convert_url = f"{self._docling_base_url}/v1/convert/file"
        logger.info(f"Using docling convert/file endpoint: {convert_url}")
        
        try:
            response = self._try_endpoint(convert_url, document_path)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Docling conversion succeeded, response keys: {list(result.keys())}")
                # Normalize external response to match localhost docling service format
                normalized_result = self._normalize_docling_response(result)
                return normalized_result
            else:
                logger.error(f"Docling endpoint returned {response.status_code}: {response.text}")
                raise Exception(f"Docling endpoint returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error calling docling conversion endpoint: {str(e)}")
            raise
    
    def _try_endpoint(self, endpoint_url: str, document_path: str):
        """Helper method to try a docling endpoint"""
        with open(document_path, 'rb') as file:
            # Docling API expects 'files' (plural) not 'file' (singular)
            files = {'files': (os.path.basename(document_path), file, 'application/octet-stream')}
            
            # Add chunking options to extract content properly
            # Based on docling configuration, we need to specify output formats
            data = {
                'chunker_options': '{"tokenizer": "huggingface", "max_chunk_size": 1000}',
                'output_formats': '["text", "markdown"]'  # Request both text and markdown content
            }
            
            # Add headers for potential authentication
            headers = {}
            docling_api_key = os.environ.get('DOCLING_API_KEY')
            if docling_api_key:
                headers['X-API-Key'] = docling_api_key
                logger.info("Using DOCLING_API_KEY for authentication")
            else:
                logger.info("No DOCLING_API_KEY found, trying without authentication")
            
            logger.info(f"Sending docling request with chunker_options and output_formats")
            response = requests.post(
                endpoint_url,
                files=files,
                data=data,
                headers=headers,
                timeout=self._docling_timeout
            )
            return response
    
    def _normalize_docling_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize external docling service responses to match localhost docling service format.
        
        Localhost format:
        {
            "md_content": "# Content here",
            "text_content": null,
            "html_content": null, 
            "json_content": null,
            "status": "success"
        }
        
        Args:
            response: Raw response from external docling service
            
        Returns:
            Normalized response matching localhost format
        """
        # If already in localhost format, return as-is
        if 'md_content' in response and 'text_content' in response:
            logger.info("Response already in localhost docling service format")
            return response
            
        # Normalize different external formats to localhost standard
        normalized = {
            "md_content": None,
            "text_content": None,
            "html_content": None,
            "json_content": None,
            "status": "success"
        }
        
        # Handle different response structures from docling API
        # Check for nested 'document' structure first
        if 'document' in response and isinstance(response['document'], dict):
            doc = response['document']
            if 'md_content' in doc and doc['md_content']:
                normalized['md_content'] = doc['md_content']
            elif 'text_content' in doc and doc['text_content']:
                normalized['md_content'] = f"# Document Content\n\n{doc['text_content']}"
            elif 'html_content' in doc and doc['html_content']:
                # Simple HTML to text conversion for fallback
                html_content = doc['html_content']
                # Basic HTML tag removal (simple approach)
                import re
                text_content = re.sub('<[^<]+?>', '', html_content)
                normalized['md_content'] = f"# Document Content\n\n{text_content.strip()}"
        
        # Fallback to direct field access
        elif 'md_content' in response and response['md_content']:
            normalized['md_content'] = response['md_content']
        elif 'markdown' in response:
            normalized['md_content'] = response['markdown']
        elif 'text_content' in response and response['text_content']:
            # Convert plain text to simple markdown format to match localhost
            text = response['text_content']
            # Add basic markdown formatting to match localhost behavior
            normalized['md_content'] = f"# Document Content\n\n{text}"
        elif 'text' in response:
            normalized['md_content'] = f"# Document Content\n\n{response['text']}"
            
        # Keep other fields null to match localhost behavior (localhost only populates md_content)
        # External services might populate these, but we normalize to localhost standard
        
        # Preserve status if available
        if 'status' in response:
            normalized['status'] = response['status']
            
        logger.info(f"Normalized external response to localhost format: md_content={'present' if normalized['md_content'] else 'null'}")
        return normalized
    
    # URL conversion method removed - not used in production pipeline
    
    def _extract_metadata_from_response(self, response_data: Dict[str, Any], upload_by="default", file_size=0) -> Dict[str, Any]:
        """
        Extract metadata from a docling endpoint response.
        
        Args:
            response_data: The response data from docling endpoint
            upload_by: User who uploaded the document
            file_size: File size in MB
            
        Returns:
            Dictionary containing document metadata
        """
        metadata = {}
        
        try:
            # Extract metadata from the endpoint response
            raw_metadata = response_data.get("metadata", {})
            if raw_metadata:
                metadata.update(raw_metadata)

            # Extract title
            metadata["title"] = raw_metadata.get("title", "Untitled")

            # Extract uploader
            metadata["upload_by"] = upload_by
            
            # Extract file size
            metadata["file_size"] = f"{file_size:.2f} MB" if file_size > 0 else "Unknown size"
                
            # Extract structural information from response
            metadata["page_count"] = raw_metadata.get("page_count", 1)
            
            # Extract content statistics
            text = response_data.get("text", "")
            metadata["character_count"] = len(text)
            metadata["word_count"] = len(text.split())
            
            # Extract table and image information if available
            metadata["table_count"] = raw_metadata.get("table_count", 0)
            metadata["image_count"] = raw_metadata.get("image_count", 0)
                
        except Exception as e:
            logger.warning(f"Error extracting metadata from response: {str(e)}")
            
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
            raw_metadata = result.get("metadata", {})
            
            structure = {
                "title": raw_metadata.get("title", "Untitled"),
                "sections": []
            }
            
            # Extract sections and subsections if available from the endpoint response
            sections = raw_metadata.get("sections", [])
            for section in sections:
                section_data = {
                    "title": section.get("title", ""),
                    "level": section.get("level", 1),
                    "text": section.get("text", ""),
                }
                structure["sections"].append(section_data)
            
            return structure
            
        except Exception as e:
            logger.error(f"Error extracting document structure: {str(e)}")
            return None
    
    def _extract_text_from_chunks(self, conversion_result: Dict[str, Any]) -> str:
        """Extract plain text from docling conversion response"""
        try:
            # First check for content in documents structure (actual docling API format)
            if 'documents' in conversion_result and conversion_result['documents']:
                document = conversion_result['documents'][0]
                content = document.get('content', {})
                text_content = content.get('text_content')
                if text_content:
                    logger.info(f"Found text_content in documents structure")
                    return text_content
            
            # Check for md_content field (localhost docling service standard format)
            if 'md_content' in conversion_result and conversion_result['md_content']:
                logger.info(f"Found md_content field (localhost docling service format)")
                # Use markdown content directly as text (matches local service behavior)
                return conversion_result['md_content']
                
            # Fallback: if external service returns text_content, use it
            elif 'text_content' in conversion_result and conversion_result['text_content']:
                logger.info(f"Found text_content field - converting to match localhost format")
                return conversion_result['text_content']
                
            # Try different possible structures for the chunking response
            elif 'chunks' in conversion_result:
                chunks = conversion_result['chunks']
                text_parts = []
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        text_parts.append(chunk.get('text', ''))
                    elif isinstance(chunk, str):
                        text_parts.append(chunk)
                if text_parts:
                    logger.info(f"Found {len(text_parts)} chunks")
                    return '\n'.join(text_parts)
            
            elif 'text' in conversion_result:
                return conversion_result['text']
                
            elif 'content' in conversion_result:
                return str(conversion_result['content'])
                
            else:
                logger.warning(f"Unknown conversion response structure: {list(conversion_result.keys())}")
                return str(conversion_result)
                
        except Exception as e:
            logger.error(f"Error extracting text from chunks: {str(e)}")
            return ""
    
    def _extract_markdown_from_chunks(self, conversion_result: Dict[str, Any]) -> str:
        """Extract markdown from docling conversion response"""
        try:
            # First check for direct md_content field (convert endpoint format)
            if 'md_content' in conversion_result and conversion_result['md_content']:
                logger.info(f"Found direct md_content field")
                return conversion_result['md_content']
                
            # Check for markdown content in documents structure
            elif 'documents' in conversion_result and conversion_result['documents']:
                document = conversion_result['documents'][0]
                content = document.get('content', {})
                md_content = content.get('md_content')
                if md_content:
                    logger.info(f"Found md_content in documents structure")
                    return md_content
                    
            # Try different possible structures for markdown content
            elif 'chunks' in conversion_result:
                chunks = conversion_result['chunks']
                markdown_parts = []
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        markdown_parts.append(chunk.get('markdown', chunk.get('text', '')))
                if markdown_parts:
                    logger.info(f"Found {len(markdown_parts)} markdown chunks")
                    return '\n\n'.join(markdown_parts)
                
            elif 'markdown' in conversion_result:
                return conversion_result['markdown']
                
            elif 'content' in conversion_result:
                return str(conversion_result['content'])
                
            else:
                # Fallback to text if no markdown found
                return self._extract_text_from_chunks(conversion_result)
                
        except Exception as e:
            logger.error(f"Error extracting markdown from chunks: {str(e)}")
            return ""