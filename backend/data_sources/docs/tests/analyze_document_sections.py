import os
import json
from shared.logger import logger
from data_sources.docs.doc_connector import DocumentConnector
from data_sources.docs.doc_config_manager import DocConfigManager
from data_sources.docs.document_processor import DocumentProcessor

input_dir = "./data/pdfs"
output_dir = "./data/section_analysis"

def analyze_document_sections() -> None:
    """
    Analyze document sections to understand document structure.
    
    This function demonstrates the section extraction capability:
    1. Extract text and metadata from documents
    2. Extract sections based on headings
    3. Save section analysis
    
    Args:
        input_dir: Directory containing PDF files
        output_dir: Directory to save section analysis
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting document section analysis for files in {input_dir}")
    
    # Initialize components
    config = DocConfigManager()
    doc_connector = DocumentConnector(config)
    doc_processor = DocumentProcessor()
    
    # Find all PDF files in the input directory
    pdf_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(input_dir, f))]
    
    # Process documents
    section_analysis = {}
    
    for pdf_file in pdf_files:
        try:
            # Get document content
            result = doc_connector.process_document(pdf_file)
            if not result:
                continue
                
            # Extract sections
            sections = doc_processor.extract_document_sections(result)
            
            # Store analysis
            filename = os.path.basename(pdf_file)
            section_analysis[filename] = {
                "num_sections": len(sections),
                "sections": [{"title": s["title"], "level": s["level"], "length": len(s["content"])} for s in sections]
            }
            
            # Save individual sections
            base_name = os.path.splitext(filename)[0]
            sections_dir = os.path.join(output_dir, base_name)
            os.makedirs(sections_dir, exist_ok=True)
            
            for i, section in enumerate(sections):
                with open(os.path.join(sections_dir, f"{i+1}_{section['title'].replace('/', '_')}.txt"), 'w', encoding='utf-8') as f:
                    f.write(section["content"])
                    
            logger.info(f"Extracted {len(sections)} sections from {filename}")
            
        except Exception as e:
            logger.error(f"Error analyzing sections for {pdf_file}: {str(e)}")
    
    # Save summary analysis
    with open(os.path.join(output_dir, "section_analysis.json"), 'w', encoding='utf-8') as f:
        json.dump(section_analysis, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Document section analysis completed successfully")