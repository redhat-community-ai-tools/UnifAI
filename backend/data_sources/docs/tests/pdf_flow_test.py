import sys
import logging

from .analyze_document_sections import analyze_document_sections
from .chunking_test import chunk_pdf_document
from .retrieval_test import rag_flow
from .embedding_test import process_documents_for_embedding
from .process_pdf_directory import process_pdf_directory
from .process_url_document import process_url_document


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('document_processing.log')
    ]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    functions = {
        "pdf_sections_analyzer": analyze_document_sections,
        "pdf_chunker": chunk_pdf_document,
        "embedding_flow": process_documents_for_embedding,
        "pdf_dir_processor": process_pdf_directory,
        "pdf_url_processor": process_url_document,
        "rag_flow": rag_flow,
    }

    if len(sys.argv) < 2:
        print("Usage: python script.py <function_name>")
        print(f"Available functions: {', '.join(functions.keys())}")
        sys.exit(1)

    func_name = sys.argv[1]
    if func_name in functions:
        functions[func_name]()
    else:
        print(f"Unknown function '{func_name}'. Available options are: {', '.join(functions.keys())}")
        sys.exit(1)