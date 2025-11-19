# Docs Data Pipeline – Test Suite

This folder contains lightweight, function-based tests that validate the key components of the **PDF data pipeline** within the `data_sources.docs` module.

## 📁 Folder Structure

├── analyze_document_sections.py
├── chunking_test.py
├── embedding_test.py
├── pdf_flow_test.py
├── process_pdf_directory.py
├── process_url_document.py
└── retrieval_test.py


## 🚀 How to Run a Test

From the backend root folder, use the following command structure:

```bash
python -m data_sources.docs.tests.pdf_flow_test <test_name>
```

### 🔧 Example
To run the RAG pipeline test:
```bash
python -m data_sources.docs.tests.pdf_flow_test rag_flow
```

### 🧪 Available Tests in pdf_flow_test.py
* analyze_document_sections – Checking how the separation into different sections of an .md file works
* chunking_test – Tests chunking logic on PDF text content
* embedding_test – Validates that embeddings are generated correctly
* process_pdf_directory - Going over all the PDFs in certain folder, proccessing them with docling
* process_url_document - Proccessing PDF file (provided from the web) with docling
* retrieval_test – Demonstrates RAG retrieval operation based on PDF chunking & embeddings

### 📝 Notes
* Each test is implemented as a **standalone Python function**.
* The pdf_flow_test.py file acts as a command-line dispatcher. Based on the provided argument, it runs the corresponding test.
* These are not formal unit tests with a testing framework like pytest, but rather scripted validation flows to confirm end-to-end functionality.