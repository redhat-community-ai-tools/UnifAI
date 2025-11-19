import re
import os
from typing import Dict, List, Any, Optional
from shared.logger import logger
from utils.data_processor import DataProcessor

class DocumentProcessor(DataProcessor):
    """
    Document processor for preparing document content for embedding.
    
    This processor cleans and normalizes document content, particularly markdown,
    and prepares text for the chunking and embedding layer.
    """
    
    def __init__(self):
        """Initialize the document processor."""
        super().__init__()
        logger.info("DocumentProcessor initialized")
        
        # Patterns for cleaning markdown content
        self._markdown_patterns = {
            "headers": r"^#+\s+.*$",
            "code_blocks": r"```.*?```",
            "tables": r"\|.*\|[\r\n]+([-|]+[\r\n]+)?(\|.*\|[\r\n]+)*",
            "links": r"\[([^\]]+)\]\(([^)]+)\)",
            "images": r"!\[([^\]]*)\]\(([^)]+)\)",
            "html_tags": r"<[^>]*>",
            "inline_code": r"`[^`]+`",
            "horizontal_rules": r"^[-*_]{3,}$",
            "blank_lines": r"\n\s*\n",
        }
        
        # Patterns for cleaning text content (for future use)
        self._text_patterns = {
            "references_section": r"(?:\n|^)References\s*\n.*?(?=\n\w+:|\Z)",
            "whitespace": r"\s+",
            "urls": r"https?://\S+",
            "page_numbers": r"\n\s*\d+\s*\n",
            "email_addresses": r"\S+@\S+\.\S+",
            "citations": r"\[\d+\]",
        }
        
    def process(self, doc: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process a single document data dictionary to prepare for embedding.

        Args:
            doc: A single document data dictionary
            **kwargs: Additional parameters specific to document processing
                - clean_markdown: Whether to clean markdown content (default: True)
                - clean_text: Whether to clean text content (default: False)
                - remove_references: Whether to remove references section (default: False)
                - preserve_original: Whether to preserve original content (default: True)
            
        Returns:
            Processed document data dictionary
        """
        # Handle case where doc is None (e.g., from failed document collection)
        if doc is None:
            logger.error("Cannot process document: doc is None (likely from failed document collection)")
            raise ValueError("Document data is None - collection phase may have failed")
        
        # Get processing options
        clean_markdown = kwargs.get("clean_markdown", True)
        clean_text = kwargs.get("clean_text", False)
        remove_references = kwargs.get("remove_references", False)
        preserve_original = kwargs.get("preserve_original", True)

        try:
            logger.info(f"Starting to process {doc.get('filename', 'Unknown')}")
            # Create a copy of the document data
            processed_doc = doc.copy() if preserve_original else {}

            # Add minimal required fields if not preserving original
            if not preserve_original:
                processed_doc["path"] = doc.get("path")
                processed_doc["filename"] = doc.get("filename")
                processed_doc["metadata"] = doc.get("metadata", {})

            # Clean markdown content if present and requested
            if "markdown" in doc and clean_markdown:
                if preserve_original:
                    processed_doc["clean_markdown"] = self.clean_markdown(doc["markdown"])
                else:
                    processed_doc["markdown"] = self.clean_markdown(doc["markdown"])

            # Clean text content if present and requested
            if "text" in doc and clean_text:
                if preserve_original:
                    processed_doc["clean_text"] = self.clean_content(doc["text"], remove_references)
                else:
                    processed_doc["text"] = self.clean_content(doc["text"], remove_references)

            # Add processing metadata
            if "metadata" not in processed_doc:
                processed_doc["metadata"] = {}

            processed_doc["metadata"]["processed"] = True
            processed_doc["metadata"]["processing_options"] = {
                "clean_markdown": clean_markdown,
                "clean_text": clean_text,
                "remove_references": remove_references,
                "preserve_original": preserve_original
            }

            logger.info(f"Successfully processed document: {doc.get('filename', 'Unknown')}")
            return processed_doc

        except Exception as e:
            logger.error(f"Error processing document {doc.get('filename', 'Unknown')}: {str(e)}")
            # Add original document with error flag
            doc["processing_error"] = str(e)
            return doc


    def process_docs(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """
        Process a list of document data dictionaries.

        Args:
            data: List of document dictionaries
            **kwargs: Processing options passed to individual `process` calls

        Returns:
            List of processed document data dictionaries
        """
        logger.info(f"Starting batch document processing for {len(data)} documents")
        processed = [self.process(doc, **kwargs) for doc in data]
        logger.info(f"Batch processing complete. Processed {len(processed)} documents")
        return processed
    
    def clean_content(self, content: str, remove_references: bool = False) -> str:
        """
        Clean and normalize plain text content.
        
        Args:
            content: Raw content text
            remove_references: Whether to remove references section
            
        Returns:
            Cleaned and normalized text
        """
        if not content:
            return ""
            
        # Make a copy of the content
        cleaned = content
        
        # Remove references section if requested
        if remove_references:
            cleaned = re.sub(self._text_patterns["references_section"], "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        # Normalize whitespace
        cleaned = re.sub(self._text_patterns["whitespace"], " ", cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def clean_markdown(self, markdown: str) -> str:
        """
        Clean and normalize markdown content.
        
        Args:
            markdown: Raw markdown content
            
        Returns:
            Cleaned markdown content
        """
        if not markdown:
            return ""
            
        # Make a copy of the markdown
        cleaned = markdown
        
        # Remove code blocks (including language identifier)
        cleaned = re.sub(self._markdown_patterns["code_blocks"], "", cleaned, flags=re.DOTALL)
        
        # Remove tables
        cleaned = re.sub(self._markdown_patterns["tables"], "", cleaned, flags=re.MULTILINE)
        
        # Replace links with just their text content
        cleaned = re.sub(self._markdown_patterns["links"], r"\1", cleaned)
        
        # Remove images
        cleaned = re.sub(self._markdown_patterns["images"], "", cleaned)
        
        # Remove HTML tags
        cleaned = re.sub(self._markdown_patterns["html_tags"], "", cleaned)
        
        # Remove inline code
        cleaned = re.sub(self._markdown_patterns["inline_code"], "", cleaned)
        
        # Remove horizontal rules
        cleaned = re.sub(self._markdown_patterns["horizontal_rules"], "", cleaned, flags=re.MULTILINE)
        
        # Normalize multiple blank lines to just one
        cleaned = re.sub(self._markdown_patterns["blank_lines"], "\n\n", cleaned)
        
        # Final trim
        cleaned = cleaned.strip()
        
        return cleaned
    
    def extract_document_sections(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract sections from a document based on headings.
        
        Args:
            doc: Document data dictionary
            
        Returns:
            List of section dictionaries with title and content
        """
        if "markdown" not in doc:
            logger.warning(f"Cannot extract sections: markdown not found in document {doc.get('filename', 'Unknown')}")
            return []
            
        markdown = doc["markdown"]
        sections = []
        current_section = {"title": "Introduction", "level": 0, "content": ""}
        
        # Pattern to match markdown headers
        header_pattern = r"^(#{1,6})\s+(.*)$"
        
        for line in markdown.split("\n"):
            match = re.match(header_pattern, line)
            if match:
                # Save previous section if it has content
                if current_section["content"].strip():
                    sections.append(current_section.copy())
                    
                # Start new section
                level = len(match.group(1))
                title = match.group(2).strip()
                current_section = {"title": title, "level": level, "content": ""}
            else:
                # Add line to current section
                current_section["content"] += line + "\n"
        
        # Add the last section
        if current_section["content"].strip():
            sections.append(current_section)
            
        logger.info(f"Extracted {len(sections)} sections from document {doc.get('filename', 'Unknown')}")
        return sections
    
    def prepare_for_single_doc_embedding(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a single processed document for embedding.

        This method extracts the key content that should be sent to the chunking and embedding layer.

        Args:
            doc: A single processed document

        Returns:
            Simplified document dictionary for embedding
        """
        try:
            # Create a simplified document for embedding
            embed_doc = {
                "id": os.path.basename(doc.get("path", "")),
                "filename": doc.get("filename", ""),
                "content": doc.get("clean_text", doc.get("text", "")),
                "metadata": {
                    "title": doc.get("metadata", {}).get("title", "Untitled"),
                    "upload_by": doc.get("metadata", {}).get("upload_by", "default"),
                    "page_count": doc.get("metadata", {}).get("page_count", 1),
                    "word_count": doc.get("metadata", {}).get("word_count", 0),
                    "source_path": doc.get("path", ""),
                }
            }
            return embed_doc

        except Exception as e:
            logger.error(f"Error preparing document for embedding: {str(e)}")
            return {}


    def prepare_for_embedding(self, processed_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare a list of processed documents for embedding.

        Args:
            processed_docs: List of processed document dictionaries

        Returns:
            List of simplified embedding document dictionaries
        """
        logger.info(f"Preparing {len(processed_docs)} documents for embedding")
        embedding_docs = [self.prepare_for_single_doc_embedding(doc) for doc in processed_docs]
        logger.info(f"Prepared {len(embedding_docs)} documents for embedding")
        return embedding_docs