# Slack Data Pipeline – Test Suite

This folder contains lightweight, function-based tests that validate the key components of the **Slack data pipeline** within the `data_sources.slack` module.

## 📁 Folder Structure
.
├── chunking_test.py        # Tests for content chunking logic
├── embedding_test.py       # Tests for embedding generation
├── logs_monitoring.py      # Tests for custom log monitoring functionality
├── retrieval_test.py       # Tests for RAG/retrieval pipeline
└── slack_flow_test.py      # Central test entry point for full Slack pipeline flows


## 🚀 How to Run a Test

From the backend root folder, use the following command structure:

```bash
python -m data_sources.slack.tests.slack_flow_test <test_name>
```

### 🔧 Example
To run the RAG pipeline test:
```bash
python -m data_sources.slack.tests.slack_flow_test rag_flow
```

### 🧪 Available Tests in slack_flow_test.py
* slack_flow – End-to-end test of the Slack ingestion and processing
* slack_chunker – Tests chunking logic on Slack message content
* embedding_flow – Validates that embeddings are generated correctly
* rag_flow – Ensures that messages are retrievable via the vector search
* monitor_logs_demo – Demonstrates the custom log monitoring system in action

### 📝 Notes
* Each test is implemented as a **standalone Python function**.
* The slack_flow_test.py file acts as a command-line dispatcher. Based on the provided argument, it runs the corresponding test.
* These are not formal unit tests with a testing framework like pytest, but rather scripted validation flows to confirm end-to-end functionality.