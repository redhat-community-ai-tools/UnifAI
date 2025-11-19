# Data Hub - Backend

## RAG Pipeline Architecture
Modular and extensible rag pipeline for integrating Jira, Slack, and document sources into vector databases for future LLM retrieval.

## High-Level Architecture
The architecture follows a modular approach with clear separation of concerns:

1. **Data Collection Layer** - Handles authentication and raw data extraction
2. **Data Processing Layer** - Processes, cleans, and normalizes data
3. **Chunking & Embedding Layer** - Splits content into appropriate chunks and creates embeddings
4. **Storage Layer** - Manages persistence to vector databases
5. **Orchestration Layer** - Coordinates the pipeline execution

## Implementation Considerations

### Modularity & Extensibility

1. **Component Interface Contracts**
    - Each component has well-defined interfaces
    - Components communicate through standardized data structures
    - New data sources can be added by implementing connector interfaces

2. **Pluggable Architecture**
    - Support for different embedding models
    - Multiple vector database options
    - Customizable chunking strategies

### Scalability

1. **Horizontal Scaling**
    - Components can be deployed independently
    - Stateless design for easy replication
    - Message queue integration for workload distribution

2. **Resource Management**
    - Efficient handling of large documents
    - Stream processing for memory efficiency
    - Batching of embedding operations

### Data Quality & Provenance

1. **Metadata Preservation**
    - Each chunk maintains source information
    - Original timestamps and authors preserved
    - Links back to original content

2. **Data Validation**
    - Input validation at each stage
    - Error handling and reporting
    - Quality metrics tracking

## Starting the BE locally:

### Prerequisite
In order to run the backend on local environment, user must to host certain containers to support the app functionality:
```bash
docker run -d --name mongo    -p 27017:27017  -v mongo_data:/data/db   mongo:5.0
docker run -d --name rabbitmq -p 5672:5672    -p 15672:15672 -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest   rabbitmq:3-management
docker run -d --name qdrant   -p 6333:6333    -p 6334:6334   -v ~/qdrant_data:/qdrant/storage   qdrant/qdrant:latest
```

1. Creating a virtual environment (e.g. virtualenv venv)
2. Getting inside the newly created venv (. ./venv/bin/activate)
3. Install backend deps (pip install -r requirements.txt)
3. Install sub-library deps (pip install -e ../global_utils/)
4. Running the backend: python app.py
5. Running celery worker: celery -A celery_app.init worker -c 1 --loglevel=info -Q slack_queue -n data_sources
6. Running celery worker: celery -A celery_app.init worker -c 1 --loglevel=info -Q docs_queue -n data_sources