import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from shared.logger import logger
from utils.data_connector import DataConnector
from .doc_config_manager import DocConfigManager
from .pdf_chunker_strategy import DoclingProcessingError
from docling.document_converter import DocumentConverter, ConversionResult, InputFormat, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend 

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
        
        # --- 1. Define Pipeline Options: Disable OCR ---
        pdf_pipeline_options = PdfPipelineOptions(
            do_ocr=False 
            # You can also pass 'artifacts_path' here if you want to redirect downloads
            # artifacts_path=config_manager.get_config("artifact_path")
        )

        pdf_format_option = PdfFormatOption(
                    pipeline_options=pdf_pipeline_options,
                    backend=PyPdfiumDocumentBackend # Forces non-OCR processing
                )

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pdf_format_option
            }
        )
        self._conversion_results: Dict[str, ConversionResult] = {}
        logger.info("DocumentConnector initialized")
    
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
        return True
    
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
            
            # Process the document with docling
            # Note: Docling's DocumentConverter.convert() doesn't accept custom parameters (those are stored in the configuration but don't passed to the method)
            logger.info(f"Using default docling conversion parameters (custom options not supported)")
            result = self._converter.convert(document_path)
            
            # Store the conversion result for future reference
            self._conversion_results[document_path] = result
            
            # Extract text and metadata
            text_content = result.document.export_to_text()
            
            # Validate that docling extracted content
            if not text_content or not text_content.strip():
                logger.error(f"Docling failed to extract text content from document: {document_path}")
                raise DoclingProcessingError(f"Docling was unable to process the provided document '{os.path.basename(document_path)}'. Failed to extract text content from the document.")
       
            document_data = {
                "text": text_content,
                "markdown": result.document.export_to_markdown(),
                "path": document_path,
                "filename": os.path.basename(document_path),
            }
            
            # Add metadata if requested
            if self._config_manager.get_config_value("include_metadata"):
                document_data["metadata"] = self._extract_metadata(result, upload_by, file_size_mb)
                
            logger.info(f"Document processed successfully: {document_path}")
            return document_data
            
        except DoclingProcessingError:
            raise
        except PdfiumError:
            # PDF cannot be opened/parsed by PDFium
            raise DoclingProcessingError("The PDF appears to be corrupted or invalid. Please upload a valid PDF.")
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
            
            # Process the document with docling
            # Note: Docling's DocumentConverter.convert() doesn't accept custom parameters
            logger.info(f"Using default docling conversion parameters (custom options not supported)")
            result = self._converter.convert(document_url)
            
            # Store the conversion result for future reference
            self._conversion_results[document_url] = result
            
            # Extract text and metadata
            text_content = result.document.export_to_text()
            
            # Validate that docling extracted meaningful content
            if not text_content or not text_content.strip():
                logger.error(f"Docling failed to extract text content from document URL: {document_url}")
                raise DoclingProcessingError(f"Docling was unable to process the provided document from URL '{document_url}'. Failed to extract text content from the document.")
                        
            document_data = {
                "text": text_content,
                "markdown": result.document.export_to_markdown(),
                "url": document_url,
            }
            
            # Add metadata if requested
            if self._config_manager.get_config_value("include_metadata"):
                document_data["metadata"] = self._extract_metadata(result)
                
            logger.info(f"Document from URL processed successfully: {document_url}")
            return document_data
            
        except DoclingProcessingError:
            raise
        except PdfiumError:
            # PDF from URL cannot be opened/parsed
            raise DoclingProcessingError("The PDF at the provided URL appears to be corrupted or invalid. Please try another file or re-upload it.")
        except Exception as e:
            logger.error(f"Error processing document from URL {document_url}: {str(e)}")
            raise DoclingProcessingError(str(e))
    
    def _extract_metadata(self, conversion_result: ConversionResult, upload_by="default", file_size=0) -> Dict[str, Any]:
        """
        Extract metadata from a conversion result.
        
        Args:
            conversion_result: The document conversion result
            
        Returns:
            Dictionary containing document metadata
        """
        metadata = {}
        
        try:
            doc = conversion_result.document
            
            # Extract basic document metadata
            if hasattr(doc, "metadata") and doc.metadata:
                metadata.update(doc.metadata)

            # Extract title
            metadata["title"] = doc.title if hasattr(doc, "title") else "Untitled"

            # Extract uploader
            metadata["upload_by"] = upload_by
            
            # Extract file size
            metadata["file_size"] = f"{file_size:.2f} MB" if file_size > 0 else "Unknown size"
                
            # Extract structural information
            metadata["page_count"] = len(doc.pages) if hasattr(doc, "pages") else 1
            
            # Extract content statistics
            text = doc.export_to_text()
            metadata["character_count"] = len(text)
            metadata["word_count"] = len(text.split())
            
            # Extract table information if available
            if hasattr(conversion_result, "tables") and conversion_result.tables:
                metadata["table_count"] = len(conversion_result.tables)
                
            # Extract image information if available
            if hasattr(conversion_result, "images") and conversion_result.images:
                metadata["image_count"] = len(conversion_result.images)
                
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
                "title": result.document.title if hasattr(result.document, "title") else "Untitled",
                "sections": []
            }
            
            # Extract sections and subsections if available
            if hasattr(result.document, "sections"):
                for section in result.document.sections:
                    section_data = {
                        "title": section.title,
                        "level": section.level if hasattr(section, "level") else 1,
                        "text": section.text if hasattr(section, "text") else "",
                    }
                    structure["sections"].append(section_data)
            
            return structure
            
        except Exception as e:
            logger.error(f"Error extracting document structure: {str(e)}")
            return None