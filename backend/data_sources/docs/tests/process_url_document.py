import os
from shared.logger import logger
from data_sources.docs.doc_config_manager import DocConfigManager
from data_sources.docs.doc_connector import DocumentConnector

document_url = "https://arxiv.org/pdf/2408.09869"
output_path = "./data/processed/arxiv_paper"

def process_url_document() -> None:
    """
    Process a document from a URL.
    
    Args:
        document_url: URL of the document to process
        output_path: Path to save processed results
    """
    logger.info(f"Processing document from URL: {document_url}")
    
    # Create custom configuration
    config = DocConfigManager()
    
    # Initialize document connector
    doc_connector = DocumentConnector(config)
    
    try:
        # Process the document from URL
        result = doc_connector.process_document_url(document_url)
        
        if result:
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save the extracted text
            with open(f"{output_path}.txt", "w", encoding="utf-8") as f:
                f.write(result["text"])
            
            # # Save as markdown
            # with open(f"{output_path}.md", "w", encoding="utf-8") as f:
            #     f.write(result["markdown"])
            
            logger.info(f"Successfully processed document from URL: {document_url}")
        else:
            logger.error(f"Failed to process document from URL: {document_url}")
            
    except Exception as e:
        logger.error(f"Error processing document from URL {document_url}: {str(e)}")