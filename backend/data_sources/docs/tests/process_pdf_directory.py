import os
from shared.logger import logger
from data_sources.docs.doc_connector import DocumentConnector
from data_sources.docs.doc_config_manager import DocConfigManager

input_dir = "./data/pdfs"
output_dir = "./data/processed"

def process_pdf_directory() -> None:
    """
    Process all PDF files in a directory.
    
    Args:
        directory_path: Path to the directory containing PDF files
        output_dir: Directory to save processed results
    """
    logger.info(f"Starting to process PDF files in {directory_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create custom configuration
    config = DocConfigManager()
    config.set_config_value("chunk_size", 1500)
    config.set_config_value("chunk_overlap", 300)

    # Note: These settings are stored in config but not used by docling currently
    # They're kept for future compatibility if docling adds these features
    config.set_config_value("extract_tables", True)
    config.set_config_value("use_ocr", True)  # Enable OCR for scanned documents
    
    # Initialize document connector with custom configuration
    doc_connector = DocumentConnector(config)
    
    # Test connection to ensure document processing is available
    if not doc_connector.test_connection():
        logger.error("Document processing is not available. Exiting.")
        return
    
    # Find all PDF files in the directory
    pdf_files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) 
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(directory_path, f))]
    
    logger.info(f"Found {len(pdf_files)} PDF files")
    
    # Process each PDF file
    for pdf_file in pdf_files:
        try:
            # Process the document
            result = doc_connector.process_document(pdf_file)
            
            if result:
                # Save the extracted text
                output_base = os.path.splitext(os.path.basename(pdf_file))[0]
                
                # Save as plain text
                with open(os.path.join(output_dir, f"{output_base}.txt"), "w", encoding="utf-8") as f:
                    f.write(result["text"])
                
                # # Save as markdown
                # with open(os.path.join(output_dir, f"{output_base}.md"), "w", encoding="utf-8") as f:
                #     f.write(result["markdown"])
                
                # Save metadata
                if "metadata" in result:
                    import json
                    with open(os.path.join(output_dir, f"{output_base}_metadata.json"), "w", encoding="utf-8") as f:
                        json.dump(result["metadata"], f, indent=2)
                
                # Get document structure
                structure = doc_connector.get_document_structure(pdf_file)
                if structure:
                    with open(os.path.join(output_dir, f"{output_base}_structure.json"), "w", encoding="utf-8") as f:
                        json.dump(structure, f, indent=2)
                
                logger.info(f"Successfully processed and saved outputs for {pdf_file}")
            else:
                logger.error(f"Failed to process {pdf_file}")
                
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {str(e)}")