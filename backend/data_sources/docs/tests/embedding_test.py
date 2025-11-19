import os
import json
from shared.logger import logger
from data_sources.docs.doc_connector import DocumentConnector
from data_sources.docs.doc_config_manager import DocConfigManager
from data_sources.docs.document_processor import DocumentProcessor

input_dir = "./data/pdfs"
output_dir = "./data/processed"

def process_documents_for_embedding() -> None:
    """
    Process documents and prepare them for embedding.
    
    This function demonstrates the complete document pipeline:
    1. Extract text and metadata from documents using DocumentConnector
    2. Clean and process the document content using DocumentProcessor
    3. Prepare the documents for chunking and embedding
    
    Args:
        input_dir: Directory containing PDF files
        output_dir: Directory to save processed results
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting document processing pipeline for files in {input_dir}")
    
    # Step 1: Initialize document connector with configuration
    config = DocConfigManager()
    doc_connector = DocumentConnector(config)
    
    # Find all PDF files in the input directory
    pdf_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(input_dir, f))]
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Step 2: Process each PDF file with the document connector
    raw_documents = []
    for pdf_file in pdf_files:
        try:
            result = doc_connector.process_document(pdf_file)
            if result:
                raw_documents.append(result)
                logger.info(f"Successfully extracted content from {pdf_file}")
            else:
                logger.error(f"Failed to extract content from {pdf_file}")
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {str(e)}")
    
    logger.info(f"Document connector processed {len(raw_documents)} out of {len(pdf_files)} documents")
    
    # Step 3: Process documents with the document processor
    doc_processor = DocumentProcessor()
    
    # Process with various options
    processed_documents = doc_processor.process_docs(
        raw_documents,
        clean_markdown=False, # Clean markdown content
        clean_text=False,     # Leave text content as is for now
        remove_references=False,  # Don't remove references yet
        preserve_original=True  # Keep original content
    )
    
    logger.info(f"Document processor completed with {len(processed_documents)} documents")
    
    # Step 4: Prepare documents for embedding
    embedding_ready_docs = doc_processor.prepare_for_embedding(processed_documents)
    
    logger.info(f"Prepared {len(embedding_ready_docs)} documents for embedding")
    
    # Step 5: Save processed documents for embedding
    embedding_file = os.path.join(output_dir, "documents_for_embedding.json")
    with open(embedding_file, 'w', encoding='utf-8') as f:
        json.dump(embedding_ready_docs, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved embedding-ready documents to {embedding_file}")
    
    # Step 6: Save processed documents for reference
    # for doc in processed_documents:
    #     try:
    #         filename = doc.get('filename', 'unknown')
    #         base_name = os.path.splitext(filename)[0]
            
    #         # Save clean markdown if available
    #         if "clean_markdown" in doc:
    #             with open(os.path.join(output_dir, f"{base_name}_clean.md"), 'w', encoding='utf-8') as f:
    #                 f.write(doc["clean_markdown"])
            
    #         # Save metadata for reference
    #         if "metadata" in doc:
    #             with open(os.path.join(output_dir, f"{base_name}_metadata.json"), 'w', encoding='utf-8') as f:
    #                 json.dump(doc["metadata"], f, indent=2, ensure_ascii=False)
                    
    #     except Exception as e:
    #         logger.error(f"Error saving processed document {filename}: {str(e)}")
            
    logger.info(f"Document processing pipeline completed successfully")