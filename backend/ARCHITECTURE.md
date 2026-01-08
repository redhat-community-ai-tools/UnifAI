# UnifAI Backend Architecture & Convention Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Architecture Patterns](#architecture-patterns)
5. [RAG Pipeline System](#rag-pipeline-system)
6. [Code Conventions](#code-conventions)
7. [API Layer](#api-layer)
8. [Data Sources](#data-sources)
9. [Storage & Persistence](#storage--persistence)
10. [Build & Deployment](#build--deployment)

---

## Overview

The UnifAI Backend (Data Pipeline Hub) is a Flask-based **RAG (Retrieval-Augmented Generation) Pipeline** system that processes and indexes data from multiple sources into vector databases for LLM retrieval.

**Core Features:**
- Multi-source data ingestion (Slack, Documents, Jira)
- Asynchronous pipeline processing with Celery
- Vector embeddings and storage (Qdrant)
- Document parsing and chunking (Docling)
- RESTful API for data source management
- Real-time pipeline status tracking

**Deployment Details:**
- **Port**: manually set, default - 13456 (mapped as `/api1` in frontend proxy), **NOTE:** for readability in this doc we will refer to the default port as the actual port
- **Architecture**: Flask + Celery workers + MongoDB + RabbitMQ + Qdrant
- **Purpose**: Document/Slack pipeline management and vector search

---

## Technology Stack

### Core Framework
- **Flask** - Lightweight web framework
- **Flask-CORS** - Cross-origin resource sharing support
- **Python 3.x** - Programming language

### Async Task Processing
- **Celery** - Distributed task queue
- **RabbitMQ** - Message broker (port 5672, management 15672)

### AI & NLP
- **LangChain 0.3.25** - LLM orchestration framework
- **LangChain-OpenAI 0.3.24** - OpenAI integration
- **Sentence Transformers** - Embedding models
- **Tiktoken** - Token counting for OpenAI models

### Document Processing
- **Docling** - Advanced document parsing (PDF, DOCX, etc.)
- **NumPy** - Numerical operations for embeddings

### Storage & Databases
- **MongoDB 5.0** - Document store (port 27017)
- **Qdrant** - Vector database (port 6333/6334)

### Authentication
- **Authlib** - OAuth/OIDC client
- **PyJWT** - JWT token handling

### Configuration & Validation
- **Pydantic 2.11.7** - Data validation and settings management
- **python-dotenv** - Environment variable management

---

## Project Structure

```
backend/
├── app.py                          # Flask application entry point
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container build configuration
├── entrypoint.sh                   # Container startup script
├── README.md                       # Setup and usage documentation
├── config/                         # Configuration management
│   └── app_config.py               # Application configuration (AppConfig class)
├── endpoints/                      # API endpoints (Flask Blueprints)
│   ├── __init__.py                 # Blueprint registration
│   ├── health.py                   # Health check endpoints
│   ├── pipelines.py                # Pipeline management API
│   ├── data_sources.py             # Data source CRUD operations
│   ├── docs.py                     # Document management API
│   ├── slack.py                    # Slack integration API
│   └── vector.py                   # Vector search operations
├── services/                       # Business logic layer
│   ├── documents/                  # Document processing services
│   ├── slack/                      # Slack integration services
│   └── slack_events/               # Slack event handlers
├── pipeline/                       # ⭐ CORE: Pipeline orchestration
│   ├── pipeline.py                 # Base pipeline interface
│   ├── pipeline_factory.py         # Pipeline factory pattern
│   ├── pipeline_executor.py        # Pipeline execution logic
│   ├── pipeline_service.py         # Pipeline service layer
│   ├── pipeline_repository.py      # Pipeline data persistence
│   ├── docs_pipeline.py            # Document pipeline implementation
│   ├── doc_pipeline_factory.py     # Document pipeline factory
│   ├── slack_pipeline.py           # Slack pipeline implementation
│   ├── slack_pipeline_factory.py   # Slack pipeline factory
│   └── decorators.py               # Pipeline decorators
├── celery_app/                     # Celery configuration
│   ├── __init__.py
│   ├── init.py                     # Celery app initialization
│   └── tasks/                      # Async task definitions
│       ├── docs_tasks.py           # Document processing tasks
│       └── slack_tasks.py          # Slack processing tasks
├── data_sources/                   # Data source connectors
│   ├── docs/                       # Document source handlers
│   └── slack/                      # Slack API integration
├── providers/                      # Data providers
│   ├── data_sources.py             # Data source provider
│   ├── docs.py                     # Document provider
│   ├── vector_stats.py             # Vector statistics provider
│   └── slack/                      # Slack data providers
├── registration/                   # Data source registration
│   └── registration_service.py     # Registration logic
├── validator/                      # Input validation
│   └── validation_schemas.py       # Pydantic schemas
├── utils/                          # Utility functions
│   ├── storage/                    # Storage utilities
│   │   └── mongo/                  # MongoDB utilities
│   ├── embeddings/                 # Embedding utilities
│   └── chunking/                   # Text chunking utilities
├── common/                         # Common utilities
│   └── constants.py                # Application constants
├── shared/                         # Shared resources
│   └── logger.py                   # Logging configuration
└── data/                           # Data storage (runtime)
    ├── uploads/                    # Uploaded files
    └── processed/                  # Processed data
```

---

## Architecture Patterns

### 1. **Layered Architecture**

The backend follows a **5-layer architecture** for clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (Flask Blueprints)              │
│  /api/health, /api/pipelines, /api/data_sources, etc.       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   Service Layer                              │
│  PipelineService, RegistrationService, DocumentService       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   Pipeline Layer                             │
│  Pipeline Factory, Executor, DocsPipeline, SlackPipeline     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   Provider Layer                             │
│  DataSourceProvider, DocsProvider, VectorStatsProvider       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   Storage Layer                              │
│  MongoDB, Qdrant, File Storage                               │
└─────────────────────────────────────────────────────────────┘
```

**Layer Responsibilities:**
- **API Layer**: Request handling, validation, response formatting
- **Service Layer**: Business logic, orchestration, transaction management
- **Pipeline Layer**: Data processing workflows, transformations
- **Provider Layer**: Data access abstraction, CRUD operations
- **Storage Layer**: Persistence mechanisms (databases, files)

### 2. **Factory Pattern for Pipelines**

Pipelines are created using the **Factory Pattern** to support multiple data source types:

```python
# pipeline_factory.py
class PipelineFactory:
    @staticmethod
    def create_pipeline(source_type: str) -> Pipeline:
        if source_type == "SLACK":
            return SlackPipelineFactory.create()
        elif source_type == "DOCUMENT":
            return DocPipelineFactory.create()
        elif source_type == "JIRA":
            return JiraPipelineFactory.create()
        else:
            raise ValueError(f"Unknown source type: {source_type}")
```

**Benefits:**
- Easy addition of new data sources
- Consistent pipeline interface
- Centralized pipeline configuration

### 3. **Celery Task Queue Architecture**

Asynchronous processing uses **Celery with RabbitMQ**:

```
┌──────────────┐         ┌─────────────┐         ┌──────────────┐
│ Flask API    │──POST──>│  RabbitMQ   │──Pull──>│ Celery Worker│
│ (Submitter)  │         │  (Broker)   │         │ (Executor)   │
└──────────────┘         └─────────────┘         └──────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │   Pipeline   │
                                                  │   Execution  │
                                                  └──────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │  Vector DB   │
                                                  │  (Qdrant)    │
                                                  └──────────────┘
```

**Queue Configuration:**
- **slack_queue**: Handles Slack data processing
- **docs_queue**: Handles document processing
- **Worker pools**: Separate workers per queue for isolation

### 4. **Configuration Management Pattern**

Configuration uses **Pydantic-based settings** with environment variable support. Upon deployment the appropriate values are being injected to the container using k8s config maps:

```python
# config/app_config.py
from global_utils.config.config import SharedConfig

class AppConfig(SharedConfig):
    # RabbitMQ Configuration
    rabbitmq_port: str = "5672"
    rabbitmq_ip: str = "0.0.0.0"
    broker_user_name: str = "guest"
    broker_password: str = "guest"
    
    # MongoDB Configuration
    mongodb_port: str = "27017"
    mongodb_ip: str = "0.0.0.0"
    
    # Flask Configuration
    hostname_local: str = "0.0.0.0"
    port: str = "13456"
    
    # Qdrant Configuration
    qdrant_ip: str = "0.0.0.0"
    qdrant_port: str = "6333"
    
    # Slack Configuration
    default_slack_bot_token: str = ""
    default_slack_user_token: str = ""
    
    # Application Configuration
    frontend_url: str = "http://localhost:5000"
    upload_folder: str = "/app/shared"
    backend_env: str = "development"
    version: str = "1.0.0"
```

**Usage:**
```python
config = AppConfig.get_instance()
port = config.port
mongo_url = f"mongodb://{config.mongodb_ip}:{config.mongodb_port}"
```

---

## RAG Pipeline System

### Overview

The **RAG (Retrieval-Augmented Generation) Pipeline** is the core feature that processes data from various sources into vector embeddings for LLM retrieval.

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────┘

1️⃣  DATA COLLECTION
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │ Slack API    │    │ File Upload  │    │ Jira API     │
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           │                   │                   │
           └───────────────────┴───────────────────┘
                                │
                                ▼
2️⃣  REGISTRATION & VALIDATION
    ┌────────────────────────────────────────────┐
    │  RegistrationService                       │
    │  - Validate source data                    │
    │  - Check for duplicates                    │
    │  - Store in MongoDB (data_sources)         │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
3️⃣  PIPELINE SUBMISSION (Celery)
    ┌────────────────────────────────────────────┐
    │  PipelineCeleryService                     │
    │  - Create Celery tasks                     │
    │  - Enqueue to appropriate queue            │
    │    (slack_queue / docs_queue)              │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
4️⃣  ASYNC EXECUTION (Celery Workers)
    ┌────────────────────────────────────────────┐
    │  Pipeline Executor                         │
    │  ┌──────────────────────────────────────┐  │
    │  │  A. Data Extraction                  │  │
    │  │     - Fetch from source              │  │
    │  │     - Parse content                  │  │
    │  └──────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────┐  │
    │  │  B. Data Cleaning & Normalization    │  │
    │  │     - Remove noise                   │  │
    │  │     - Standardize format             │  │
    │  └──────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────┐  │
    │  │  C. Chunking                         │  │
    │  │     - Split into appropriate chunks  │  │
    │  │     - Preserve metadata              │  │
    │  └──────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────┐  │
    │  │  D. Embedding Generation             │  │
    │  │     - Generate embeddings            │  │
    │  │     - Batch processing               │  │
    │  └──────────────────────────────────────┘  │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
5️⃣  VECTOR STORAGE
    ┌────────────────────────────────────────────┐
    │  Qdrant Vector Database                    │
    │  - Store embeddings                        │
    │  - Create collection if needed             │
    │  - Index for fast retrieval                │
    └────────────────────────────────────────────┘
```

### Pipeline Components

#### 1. **Data Collection Layer**

Handles authentication and raw data extraction from sources.

**Slack Connector:**
```python
# data_sources/slack/slack_connector.py
class SlackConnector:
    def __init__(self, bot_token: str, user_token: str):
        self.client = WebClient(token=bot_token)
        self.user_client = WebClient(token=user_token)
    
    def fetch_channels(self) -> List[Dict]:
        """Fetch all accessible channels"""
        response = self.client.conversations_list()
        return response['channels']
    
    def fetch_messages(self, channel_id: str, limit: int = 100) -> List[Dict]:
        """Fetch messages from a channel"""
        response = self.client.conversations_history(
            channel=channel_id,
            limit=limit
        )
        return response['messages']
```

**Document Uploader:**
```python
# services/documents/document_service.py
class DocumentService:
    def upload_documents(self, files: List[FileStorage], user_id: str) -> Dict:
        """
        Upload documents to storage
        
        Args:
            files: List of uploaded files
            user_id: User who uploaded the files
            
        Returns:
            Upload status and file metadata
        """
        uploaded_files = []
        for file in files:
            # Validate file type
            if not self._is_valid_file_type(file.filename):
                raise ValueError(f"Invalid file type: {file.filename}")
            
            # Save to upload folder
            file_path = os.path.join(self.upload_folder, file.filename)
            file.save(file_path)
            
            # Store metadata
            uploaded_files.append({
                "filename": file.filename,
                "path": file_path,
                "size": os.path.getsize(file_path),
                "uploaded_by": user_id,
                "uploaded_at": datetime.now()
            })
        
        return {"uploaded_files": uploaded_files, "count": len(uploaded_files)}
```

#### 2. **Registration & Validation**

Validates and persists data source metadata.

```python
# registration/registration_service.py
class RegistrationService:
    def register_sources(
        self, 
        data_list: List[Dict], 
        source_type: str, 
        upload_by: str
    ) -> Dict:
        """
        Register data sources in MongoDB
        
        Args:
            data_list: List of data sources to register
            source_type: Type of source (SLACK, DOCUMENT, JIRA)
            upload_by: User who initiated registration
            
        Returns:
            Registration status and registered sources
        """
        registered_sources = []
        for data in data_list:
            # Check for duplicates
            existing = self._find_existing_source(data, source_type)
            if existing:
                logger.info(f"Source already exists: {data['source_name']}")
                continue
            
            # Create source document
            source_doc = {
                "source_type": source_type,
                "source_name": data['source_name'],
                "source_id": data.get('source_id'),
                "metadata": data.get('metadata', {}),
                "status": "registered",
                "uploaded_by": upload_by,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            # Save to MongoDB
            result = self.mongo_storage.insert_one("data_sources", source_doc)
            source_doc['_id'] = str(result.inserted_id)
            registered_sources.append(source_doc)
        
        return {
            "registered_sources": registered_sources,
            "count": len(registered_sources),
            "skipped": len(data_list) - len(registered_sources)
        }
```

#### 3. **Pipeline Execution**

Processes data through multiple stages.

**Base Pipeline Interface:**
```python
# pipeline/pipeline.py
from abc import ABC, abstractmethod

class Pipeline(ABC):
    """Base pipeline interface for all data source pipelines"""
    
    @abstractmethod
    def extract(self, source: Dict) -> List[Dict]:
        """Extract raw data from source"""
        pass
    
    @abstractmethod
    def transform(self, data: List[Dict]) -> List[Dict]:
        """Transform and clean data"""
        pass
    
    @abstractmethod
    def chunk(self, data: List[Dict]) -> List[Dict]:
        """Chunk data into appropriate sizes"""
        pass
    
    @abstractmethod
    def embed(self, chunks: List[Dict]) -> List[Dict]:
        """Generate embeddings for chunks"""
        pass
    
    @abstractmethod
    def load(self, embeddings: List[Dict]) -> Dict:
        """Load embeddings into vector database"""
        pass
    
    def execute(self, source: Dict) -> Dict:
        """Execute the full pipeline"""
        try:
            data = self.extract(source)
            transformed = self.transform(data)
            chunks = self.chunk(transformed)
            embeddings = self.embed(chunks)
            result = self.load(embeddings)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            return {"status": "failed", "error": str(e)}
```

**Document Pipeline Implementation:**
```python
# pipeline/docs_pipeline.py
class DocsPipeline(Pipeline):
    def __init__(self, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.embedding_model = SentenceTransformer(embedding_model)
        self.qdrant_client = QdrantClient(host=config.qdrant_ip, port=config.qdrant_port)
        self.docling_parser = DocumentParser()
    
    def extract(self, source: Dict) -> List[Dict]:
        """Extract text from documents using Docling"""
        file_path = source['file_path']
        
        # Use Docling for advanced document parsing
        parsed_doc = self.docling_parser.parse(file_path)
        
        return [{
            "content": parsed_doc.text,
            "metadata": {
                "filename": source['source_name'],
                "source_id": source['_id'],
                "page_count": parsed_doc.page_count,
                "parsed_at": datetime.now()
            }
        }]
    
    def transform(self, data: List[Dict]) -> List[Dict]:
        """Clean and normalize text"""
        for item in data:
            # Remove extra whitespace
            item['content'] = re.sub(r'\s+', ' ', item['content']).strip()
            
            # Normalize unicode
            item['content'] = unicodedata.normalize('NFKC', item['content'])
        
        return data
    
    def chunk(self, data: List[Dict]) -> List[Dict]:
        """Split documents into chunks using LangChain text splitter"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        chunks = []
        for item in data:
            splits = text_splitter.split_text(item['content'])
            for idx, split in enumerate(splits):
                chunks.append({
                    "content": split,
                    "metadata": {
                        **item['metadata'],
                        "chunk_index": idx,
                        "total_chunks": len(splits)
                    }
                })
        
        return chunks
    
    def embed(self, chunks: List[Dict]) -> List[Dict]:
        """Generate embeddings using Sentence Transformers"""
        texts = [chunk['content'] for chunk in chunks]
        
        # Batch processing for efficiency
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True
        )
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding.tolist()
        
        return chunks
    
    def load(self, embeddings: List[Dict]) -> Dict:
        """Store embeddings in Qdrant"""
        collection_name = "documents"
        
        # Create collection if it doesn't exist
        try:
            self.qdrant_client.get_collection(collection_name)
        except:
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "size": len(embeddings[0]['embedding']),
                    "distance": "Cosine"
                }
            )
        
        # Prepare points
        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": emb['embedding'],
                "payload": {
                    "content": emb['content'],
                    "metadata": emb['metadata']
                }
            }
            for emb in embeddings
        ]
        
        # Upload to Qdrant
        self.qdrant_client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        return {
            "collection": collection_name,
            "points_uploaded": len(points)
        }
```

#### 4. **Celery Task Orchestration**

Asynchronous task execution with Celery.

```python
# celery_app/init.py
from celery import Celery
from config.app_config import AppConfig

config = AppConfig.get_instance()

celery_app = Celery(
    'unifai_backend',
    broker=f'amqp://{config.broker_user_name}:{config.broker_password}@{config.rabbitmq_ip}:{config.rabbitmq_port}//',
    backend=f'mongodb://{config.mongodb_ip}:{config.mongodb_port}/celery_results',
    include=['celery_app.tasks.docs_tasks', 'celery_app.tasks.slack_tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'celery_app.tasks.docs_tasks.*': {'queue': 'docs_queue'},
        'celery_app.tasks.slack_tasks.*': {'queue': 'slack_queue'}
    }
)
```

**Document Processing Task:**
```python
# celery_app/tasks/docs_tasks.py
from celery_app.init import celery_app
from pipeline.doc_pipeline_factory import DocPipelineFactory

@celery_app.task(name='process_document', bind=True)
def process_document(self, source_data: Dict):
    """
    Celery task for processing a document through the pipeline
    
    Args:
        source_data: Document metadata from MongoDB
        
    Returns:
        Pipeline execution result
    """
    try:
        # Update status to processing
        update_source_status(source_data['_id'], "processing")
        
        # Create and execute pipeline
        pipeline = DocPipelineFactory.create()
        result = pipeline.execute(source_data)
        
        # Update status based on result
        if result['status'] == 'success':
            update_source_status(source_data['_id'], "completed", result)
        else:
            update_source_status(source_data['_id'], "failed", result)
        
        return result
    except Exception as e:
        update_source_status(source_data['_id'], "failed", {"error": str(e)})
        raise
```

---

## Code Conventions

### File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Modules | snake_case.py | `pipeline_executor.py` |
| Classes | PascalCase | `PipelineFactory`, `DocumentService` |
| Functions | snake_case | `execute_pipeline()`, `fetch_channels()` |
| Constants | UPPER_SNAKE_CASE | `MAX_CHUNK_SIZE`, `DEFAULT_EMBEDDING_MODEL` |
| Blueprints | snake_case_bp | `pipelines_bp`, `health_bp` |

### Python Style Guide

**Import Order:**
```python
# 1. Standard library imports
import os
import sys
from typing import List, Dict, Optional
from datetime import datetime

# 2. Third-party imports
from flask import Blueprint, jsonify, request
from celery import Celery
import numpy as np

# 3. Local application imports
from config.app_config import AppConfig
from pipeline.pipeline_factory import PipelineFactory
from shared.logger import logger
```

**Class Structure:**
```python
class DocumentService:
    """
    Service for document management operations
    
    Attributes:
        upload_folder: Directory for uploaded files
        mongo_storage: MongoDB storage instance
    """
    
    def __init__(self, upload_folder: str):
        """Initialize document service"""
        self.upload_folder = upload_folder
        self.mongo_storage = MongoStorage()
        self._logger = logger
    
    def upload_documents(self, files: List[FileStorage], user_id: str) -> Dict:
        """
        Upload documents to storage
        
        Args:
            files: List of uploaded files
            user_id: User who uploaded the files
            
        Returns:
            Upload status and file metadata
            
        Raises:
            ValueError: If file type is invalid
        """
        # Implementation
        pass
    
    def _is_valid_file_type(self, filename: str) -> bool:
        """Private helper method for file validation"""
        # Implementation
        pass
```

**Error Handling:**
```python
# ✅ Correct: Specific exception handling with logging
try:
    result = pipeline.execute(source)
except ValueError as e:
    logger.error(f"Invalid source data: {str(e)}")
    return {"error": "Invalid source data", "details": str(e)}, 400
except ConnectionError as e:
    logger.error(f"Database connection failed: {str(e)}")
    return {"error": "Service unavailable", "details": str(e)}, 503
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return {"error": "Internal server error"}, 500
```

**Type Hints:**
```python
# ✅ Use type hints for function signatures
from typing import List, Dict, Optional, Union

def process_documents(
    files: List[str],
    user_id: str,
    options: Optional[Dict] = None
) -> Dict[str, Union[int, str, List]]:
    """Process documents with type safety"""
    pass
```

**Docstrings (Google Style):**
```python
def execute_pipeline(source: Dict, pipeline_type: str) -> Dict:
    """
    Execute a data processing pipeline
    
    Args:
        source: Source data dictionary containing metadata
        pipeline_type: Type of pipeline to execute (SLACK, DOCUMENT, JIRA)
    
    Returns:
        Dictionary containing execution status and results:
        {
            "status": "success" | "failed",
            "result": {...},
            "error": str (if failed)
        }
    
    Raises:
        ValueError: If pipeline_type is not supported
        ConnectionError: If unable to connect to storage
    
    Example:
        >>> source = {"source_name": "doc.pdf", "file_path": "/uploads/doc.pdf"}
        >>> result = execute_pipeline(source, "DOCUMENT")
        >>> print(result['status'])
        'success'
    """
    pass
```

### Flask Blueprint Pattern

**Blueprint Definition:**
```python
# endpoints/pipelines.py
from flask import Blueprint, jsonify, request
from webargs import fields
from global_utils.helpers.apiargs import from_body

pipelines_bp = Blueprint("pipelines", __name__)

@pipelines_bp.route("/embed", methods=["PUT"])
@from_body({
    "data": fields.List(fields.Dict(), required=True),
    "source_type": fields.Str(required=True),
    "logged_in_user": fields.Str(required=True),
})
def start_pipeline(data, source_type, logged_in_user):
    """Trigger the embedding pipeline"""
    try:
        # Implementation
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to start pipeline: {str(e)}")
        return jsonify({"error": str(e)}), 500
```

**Blueprint Registration:**
```python
# endpoints/__init__.py
from endpoints.health import health_bp
from endpoints.pipelines import pipelines_bp
from endpoints.data_sources import data_sources_bp
from endpoints.docs import docs_bp
from endpoints.slack import slack_bp
from endpoints.vector import vector_bp

def register_all_endpoints(app):
    """Register all Flask blueprints"""
    app.register_blueprint(health_bp, url_prefix='/api/health')
    app.register_blueprint(pipelines_bp, url_prefix='/api/pipelines')
    app.register_blueprint(data_sources_bp, url_prefix='/api/data_sources')
    app.register_blueprint(docs_bp, url_prefix='/api/docs')
    app.register_blueprint(slack_bp, url_prefix='/api/slack')
    app.register_blueprint(vector_bp, url_prefix='/api/vector')
```

---

## API Layer

### Endpoint Naming Convention

UnifAI backend uses **dot-notation** for endpoint names (matching frontend expectations):

```
/api/data_sources/data.sources.get
/api/pipelines/embed
/api/docs/upload
/api/slack/channels.list
/api/vector/search
```

### Request/Response Patterns

**GET with Query Parameters:**
```python
@data_sources_bp.route("/data.sources.get", methods=["GET"])
def get_data_sources():
    """
    Get data sources for a user
    
    Query params:
        source_type: Filter by source type (optional)
        user_id: User ID (required)
    """
    source_type = request.args.get('source_type')
    user_id = request.args.get('user_id')
    
    # Implementation
    return jsonify({"sources": sources, "count": len(sources)}), 200
```

**POST with JSON Body:**
```python
@pipelines_bp.route("/embed", methods=["PUT"])
@from_body({
    "data": fields.List(fields.Dict(), required=True),
    "source_type": fields.Str(required=True),
    "logged_in_user": fields.Str(required=True),
})
def start_pipeline(data, source_type, logged_in_user):
    """Start embedding pipeline"""
    # Implementation
    return jsonify(result), 200
```

**File Upload:**
```python
@docs_bp.route("/upload", methods=["POST"])
def upload_documents():
    """
    Upload documents
    
    Form data:
        files: List of files
        user_id: User ID
    """
    files = request.files.getlist('files')
    user_id = request.form.get('user_id')
    
    # Implementation
    return jsonify({"uploaded": len(files)}), 200
```

### API Response Format

**Success Response:**
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": "Error message",
  "details": "Detailed error information",
  "code": "ERROR_CODE"
}
```

### Endpoint Documentation

#### Health Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health/` | GET | Health check |
| `/api/health/version` | GET | Get application version |

#### Pipeline Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipelines/embed` | PUT | Start embedding pipeline |

#### Data Source Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/data_sources/data.sources.get` | GET | List data sources |
| `/api/data_sources/data.sources.create` | POST | Create data source |
| `/api/data_sources/data.sources.delete` | DELETE | Delete data source |

#### Document Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/docs/upload` | POST | Upload documents |
| `/api/docs/list` | GET | List uploaded documents |
| `/api/docs/delete` | DELETE | Delete document |

#### Slack Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/slack/channels.list` | GET | List Slack channels |
| `/api/slack/messages.fetch` | POST | Fetch channel messages |

#### Vector Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vector/search` | POST | Search vectors |
| `/api/vector/stats` | GET | Get collection statistics |

---

## Data Sources

### Supported Data Sources

1. **Slack**
   - Channel messages
   - Thread conversations
   - User mentions
   - File attachments

2. **Documents**
   - PDF files (via Docling)
   - Word documents (.docx)
   - Text files (.txt)
   - Markdown files (.md)

3. **Jira** (planned)
   - Issues
   - Comments
   - Attachments

### Data Source Schema

**MongoDB Collection: `data_sources`**

```python
{
    "_id": ObjectId("..."),
    "source_type": "SLACK" | "DOCUMENT" | "JIRA",
    "source_name": str,  # Channel name, filename, etc.
    "source_id": str,    # External ID (channel ID, file path, etc.)
    "metadata": {
        # Source-specific metadata
    },
    "status": "registered" | "processing" | "completed" | "failed",
    "uploaded_by": str,
    "created_at": datetime,
    "updated_at": datetime,
    "processing_result": {
        "chunks_created": int,
        "embeddings_generated": int,
        "errors": List[str]
    }
}
```

---

## Storage & Persistence

### MongoDB

**Purpose**: Document storage for metadata and application data

**Collections:**
- `data_sources`: Data source registry
- `users`: User information
- `pipelines`: Pipeline execution history
- `celery_results`: Celery task results

**Connection:**
```python
from utils.storage.mongo.mongo_storage import MongoStorage

mongo = MongoStorage()
result = mongo.insert_one("data_sources", document)
sources = mongo.find("data_sources", {"user_id": user_id})
```

### Qdrant Vector Database

**Purpose**: Vector embeddings storage for semantic search

**Collections:**
- `documents`: Document embeddings
- `slack_messages`: Slack message embeddings
- `jira_issues`: Jira issue embeddings (planned)

**Connection:**
```python
from qdrant_client import QdrantClient

qdrant = QdrantClient(host=config.qdrant_ip, port=config.qdrant_port)

# Create collection
qdrant.create_collection(
    collection_name="documents",
    vectors_config={
        "size": 384,  # Embedding dimension
        "distance": "Cosine"
    }
)

# Upsert vectors
qdrant.upsert(
    collection_name="documents",
    points=[
        {
            "id": "uuid",
            "vector": [0.1, 0.2, ...],
            "payload": {"content": "...", "metadata": {...}}
        }
    ]
)

# Search
results = qdrant.search(
    collection_name="documents",
    query_vector=[0.1, 0.2, ...],
    limit=10
)
```

### File Storage

**Upload Folder**: `/app/shared` (in container) or configured via `AppConfig.upload_folder`

**Structure:**
```
/app/shared/
├── uploads/          # Uploaded files
│   ├── user_123/     # User-specific folders
│   │   ├── doc1.pdf
│   │   └── doc2.pdf
└── processed/        # Processed files
    └── user_123/
        ├── doc1_chunks.json
        └── doc2_chunks.json
```

---

## Build & Deployment

### Local Development

**Prerequisites:**
```bash
# Start required services
docker run -d --name mongo    -p 27017:27017  -v mongo_data:/data/db   mongo:5.0
docker run -d --name rabbitmq -p 5672:5672    -p 15672:15672 \
    -e RABBITMQ_DEFAULT_USER=guest \
    -e RABBITMQ_DEFAULT_PASS=guest \
    rabbitmq:3-management
docker run -d --name qdrant   -p 6333:6333    -p 6334:6334 \
    -v ~/qdrant_data:/qdrant/storage \
    qdrant/qdrant:latest
```

**Setup:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e ../global_utils/

# Set environment variables (optional, uses defaults from AppConfig)
export MONGODB_IP=localhost
export QDRANT_IP=localhost
export RABBITMQ_IP=localhost
```

**Run Flask App:**
```bash
python app.py
# Runs on http://0.0.0.0:13456
```

**Run Celery Workers:**

Terminal 1 (Slack queue):
```bash
celery -A celery_app.init worker -c 1 --loglevel=info -Q slack_queue -n slack_worker
```

Terminal 2 (Docs queue):
```bash
celery -A celery_app.init worker -c 1 --loglevel=info -Q docs_queue -n docs_worker
```

### Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy global_utils
COPY ../global_utils /global_utils
RUN pip install -e /global_utils

# Expose port
EXPOSE 13456

# Run entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
```

**entrypoint.sh:**
```bash
#!/bin/bash

# Start Flask application
python app.py
```

**Build and Run:**
```bash
# Build image
docker build -t unifai-backend:latest .

# Run container
docker run -d \
    --name unifai-backend \
    -p 13456:13456 \
    -e MONGODB_IP=mongo \
    -e QDRANT_IP=qdrant \
    -e RABBITMQ_IP=rabbitmq \
    --network unifai-network \
    unifai-backend:latest
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_IP` | `0.0.0.0` | MongoDB host |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `QDRANT_IP` | `0.0.0.0` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `RABBITMQ_IP` | `0.0.0.0` | RabbitMQ host |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `BROKER_USER_NAME` | `guest` | RabbitMQ username |
| `BROKER_PASSWORD` | `guest` | RabbitMQ password |
| `FRONTEND_URL` | `http://localhost:5000` | Frontend URL for CORS |
| `UPLOAD_FOLDER` | `/app/shared` | File upload directory |
| `DEFAULT_SLACK_BOT_TOKEN` | _(empty)_ | Slack bot token |
| `DEFAULT_SLACK_USER_TOKEN` | _(empty)_ | Slack user token |
| `BACKEND_ENV` | `development` | Environment (development/production) |
| `VERSION` | `1.0.0` | Application version |

### Deployment with Helm

**See `helm/` directory and CI/CD pipeline documentation**

The backend is deployed as part of the UnifAI Helm chart:
- Deployment: `unifai-dataflow-server`
- Service: `unifai-dataflow-service`
- Workers: `unifai-dataflow-celery-workers` (separate pods)

---

## Best Practices

### 1. **Pipeline Design**

```python
# ✅ Use factory pattern for extensibility
pipeline = PipelineFactory.create_pipeline(source_type)

# ✅ Implement error handling at each stage
def execute(self, source: Dict) -> Dict:
    try:
        data = self.extract(source)
    except Exception as e:
        logger.error(f"Extract failed: {e}")
        return {"status": "failed", "stage": "extract", "error": str(e)}
    # ... continue with other stages
```

### 2. **Async Processing**

```python
# ✅ Use Celery for long-running tasks
@celery_app.task
def process_large_document(source_id: str):
    # Long-running task
    pass

# ❌ Avoid blocking API endpoints
@app.route("/process", methods=["POST"])
def process():
    # DON'T DO THIS - blocks the server
    result = heavy_computation()
    return jsonify(result)
```

### 3. **Database Operations**

```python
# ✅ Use connection pooling
mongo = MongoStorage()  # Singleton pattern

# ✅ Index frequently queried fields
mongo.create_index("data_sources", [("user_id", 1), ("source_type", 1)])

# ✅ Use projections to limit data transfer
sources = mongo.find("data_sources", {"user_id": user_id}, projection={"source_name": 1})
```

### 4. **Error Handling**

```python
# ✅ Log errors with context
try:
    result = process_data(data)
except Exception as e:
    logger.error(
        f"Processing failed for user {user_id}",
        extra={"user_id": user_id, "data": data},
        exc_info=True
    )
    raise

# ✅ Return meaningful error messages to API clients
return jsonify({
    "error": "Processing failed",
    "details": str(e),
    "retry_after": 300  # seconds
}), 500
```

### 5. **Configuration Management**

```python
# ✅ Use centralized configuration
config = AppConfig.get_instance()

# ✅ Support environment variable overrides
# Set via: export MONGODB_IP=production-mongo

# ❌ Don't hardcode values
mongodb_url = "mongodb://localhost:27017"  # BAD
```

---

## Troubleshooting

### Common Issues

#### 1. **Celery Worker Not Processing Tasks**

**Symptom:** Tasks stay in pending state

**Solution:**
```bash
# Check RabbitMQ is running
curl http://localhost:15672/api/overview
# Login: guest/guest

# Check worker is connected
celery -A celery_app.init inspect active

# Restart worker with correct queue
celery -A celery_app.init worker -Q docs_queue -n docs_worker --loglevel=debug
```

#### 2. **MongoDB Connection Failed**

**Symptom:** `ConnectionError: Could not connect to MongoDB`

**Solution:**
```bash
# Check MongoDB is running
docker ps | grep mongo

# Test connection
mongosh --host localhost --port 27017

# Verify network connectivity (in Docker)
docker network inspect unifai-network
```

#### 3. **Qdrant Collection Not Found**

**Symptom:** `CollectionNotFound: Collection 'documents' does not exist`

**Solution:**
```python
# Create collection if not exists
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)

try:
    client.get_collection("documents")
except:
    client.create_collection(
        collection_name="documents",
        vectors_config={"size": 384, "distance": "Cosine"}
    )
```

#### 4. **File Upload Fails**

**Symptom:** `FileNotFoundError` or permission denied

**Solution:**
```bash
# Create upload directory
mkdir -p /app/shared/uploads
chmod 777 /app/shared/uploads

# Check Flask configuration
config = AppConfig.get_instance()
print(config.upload_folder)
```

#### 5. **Pipeline Execution Timeout**

**Symptom:** Celery task times out

**Solution:**
```python
# Increase task timeout in Celery config
celery_app.conf.update(
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000  # 50 minutes
)

# Or set per-task
@celery_app.task(time_limit=7200)
def process_large_document(source_id: str):
    pass
```

---

## Code Review Checklist

When reviewing backend PRs:

### General
- [ ] Code follows Python PEP 8 style guide
- [ ] Type hints provided for function signatures
- [ ] Docstrings provided (Google style)
- [ ] Imports organized (stdlib → third-party → local)
- [ ] No hardcoded values (use AppConfig)

### API Endpoints
- [ ] Blueprint registered in `endpoints/__init__.py`
- [ ] Input validation with `@from_body` or request validation
- [ ] Error handling with appropriate HTTP status codes
- [ ] Logging for errors and important operations
- [ ] CORS headers configured (if needed)

### Pipeline Implementation
- [ ] Implements `Pipeline` interface
- [ ] Error handling at each stage (extract, transform, chunk, embed, load)
- [ ] Metadata preserved through pipeline
- [ ] Factory pattern used for pipeline creation
- [ ] Unit tests provided

### Celery Tasks
- [ ] Task decorated with `@celery_app.task`
- [ ] Task name specified explicitly
- [ ] Routed to correct queue
- [ ] Timeout configured appropriately
- [ ] Status updates tracked in database

### Database Operations
- [ ] Uses connection pooling (MongoStorage singleton)
- [ ] Indexes created for frequently queried fields
- [ ] Projections used to limit data transfer
- [ ] Transactions used for multi-document operations (if needed)
- [ ] Error handling for connection failures

### Performance
- [ ] Batch operations for embeddings
- [ ] Lazy loading for large datasets
- [ ] Async operations use Celery (not blocking endpoints)
- [ ] Database queries optimized (indexed fields, projections)

### Security
- [ ] Input validation on all endpoints
- [ ] File uploads validated (type, size)
- [ ] SQL injection prevention (using parameterized queries)
- [ ] Sensitive data not logged
- [ ] Authentication/authorization checked (if applicable)

---

## Glossary

| Term | Definition |
|------|------------|
| **RAG** | Retrieval-Augmented Generation - technique combining retrieval from vector DB with LLM generation |
| **Embedding** | Vector representation of text for semantic similarity |
| **Chunking** | Splitting documents into smaller pieces for embedding |
| **Vector Database** | Database optimized for storing and searching vector embeddings |
| **Celery** | Distributed task queue for Python |
| **RabbitMQ** | Message broker for Celery task distribution |
| **Qdrant** | Open-source vector database for similarity search |
| **Docling** | Document parsing library for extracting text from various formats |
| **Blueprint** | Flask's modular way of organizing routes and handlers |
| **Pipeline** | Multi-stage data processing workflow |
| **Factory Pattern** | Design pattern for creating objects without specifying exact class |

---

## Contact & Support

For questions about this architecture document or backend conventions:

1. **Architecture questions**: Review this document, check `README.md` in `/backend`
2. **Pipeline implementation**: Check `/backend/pipeline` directory and base `Pipeline` class
3. **API endpoints**: Review `/backend/endpoints` and endpoint documentation
4. **Celery tasks**: Check `/backend/celery_app/tasks` for examples
5. **Build issues**: Verify dependencies in `requirements.txt`, check Docker logs

---

**Document Version:** 1.0  
**Last Updated:** December 17, 2025  
**Maintainer:** UnifAI Development Team

