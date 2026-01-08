# 🚀 UnifAI Backend - Data Pipeline Hub

Welcome! This is the **Data Pipeline Hub** backend, a Flask-based RAG (Retrieval-Augmented Generation) pipeline system for processing and indexing data from multiple sources into vector databases for LLM retrieval.

> **📖 For detailed architecture, conventions, and troubleshooting, see [ARCHITECTURE.md](./ARCHITECTURE.md)**

---

## 📦 Overview

The UnifAI Backend provides a modular and extensible pipeline for integrating **Jira**, **Slack**, and **document sources** into vector databases for future LLM retrieval.

**Core Features:**
- Multi-source data ingestion (Slack, Documents, Jira)
- Asynchronous pipeline processing with Celery
- Vector embeddings and storage (Qdrant)
- Document parsing and chunking (Docling)
- RESTful API for data source management

**Quick Links:**
- 📚 [Detailed Architecture Documentation](./ARCHITECTURE.md)
- 🔧 [Configuration Guide](#configuration)
- 🐛 [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

The architecture follows a **5-layer modular approach** with clear separation of concerns:

1. **Data Collection Layer** - Handles authentication and raw data extraction
2. **Data Processing Layer** - Processes, cleans, and normalizes data
3. **Chunking & Embedding Layer** - Splits content into appropriate chunks and creates embeddings
4. **Storage Layer** - Manages persistence to vector databases
5. **Orchestration Layer** - Coordinates the pipeline execution

### Key Design Principles

**Modularity & Extensibility:**
- Each component has well-defined interfaces
- Components communicate through standardized data structures
- New data sources can be added by implementing connector interfaces
- Support for different embedding models and vector database options

**Scalability:**
- Components can be deployed independently
- Stateless design for easy replication
- Message queue integration (RabbitMQ) for workload distribution
- Efficient handling of large documents with stream processing

**Data Quality & Provenance:**
- Each chunk maintains source information
- Original timestamps and authors preserved
- Links back to original content
- Input validation at each stage with quality metrics tracking

---

## 🛠️ Prerequisites

Before running the backend locally, you need to have certain containers to support the app functionality. It's possible to either use a locally hosted services or use existing ones (in that case the configuration/env should be updated accordingly)

### Required Services

**MongoDB** (Document storage):
```bash
docker run -d --name mongo \
  -p 27017:27017 \
  -v mongo_data:/data/db \
  mongo:5.0
```

**RabbitMQ** (Message broker for Celery):
```bash
docker run -d --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest \
  -e RABBITMQ_DEFAULT_PASS=guest \
  rabbitmq:3-management
```

**Qdrant** (Vector database):
```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v ~/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest
```

### Management Interfaces

After starting the services, you can access:
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **MongoDB**: mongodb://localhost:27017
- **Qdrant Dashboard**: http://localhost:6333/dashboard

---

## 🚀 Getting Started

### 1. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Install backend dependencies
pip install -r requirements.txt

# Install sub-library dependencies (global utilities)
pip install -e ../global_utils/
```

### 3. Configure Environment (Optional)

By default, the backend uses configuration from `config/app_config.py`. You can override settings using environment variables:

```bash
# Example: Set custom service addresses
export MONGODB_IP=localhost
export MONGODB_PORT=27017
export QDRANT_IP=localhost
export QDRANT_PORT=6333
export RABBITMQ_IP=localhost
export RABBITMQ_PORT=5672

# Slack tokens (get from genie-cred-data)
export DEFAULT_SLACK_BOT_TOKEN="xoxb-..."
export DEFAULT_SLACK_USER_TOKEN="xoxp-..."

# Frontend URL for CORS
export FRONTEND_URL="http://localhost:5000"
```

### 4. Run the Flask Application

```bash
python app.py
```

The backend will start on **http://0.0.0.0:13456** (default port).

### 5. Run Celery Workers

Open **two separate terminals** (keep virtual environment activated) and run:

**Terminal 1 - Slack Queue Worker:**
```bash
celery -A celery_app.init worker -c 1 --loglevel=info -Q slack_queue -n slack_worker
```

**Terminal 2 - Docs Queue Worker:**
```bash
celery -A celery_app.init worker -c 1 --loglevel=info -Q docs_queue -n docs_worker
```

---

## 🔧 Configuration

### Configuration File

Main configuration is in `config/app_config.py`:

```python
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
    
    # Application Settings
    frontend_url: str = "http://localhost:5000"
    upload_folder: str = "/app/shared"
    version: str = "1.0.0"
```

### Environment Variables

All configuration values can be overridden using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_IP` | `0.0.0.0` | MongoDB host address |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `QDRANT_IP` | `0.0.0.0` | Qdrant host address |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `RABBITMQ_IP` | `0.0.0.0` | RabbitMQ host address |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `FRONTEND_URL` | `http://localhost:5000` | Frontend URL for CORS |
| `DEFAULT_SLACK_BOT_TOKEN` | _(empty)_ | Slack bot OAuth token |
| `DEFAULT_SLACK_USER_TOKEN` | _(empty)_ | Slack user OAuth token |

**Note:** Upon deployment, appropriate values are injected into the container using Kubernetes ConfigMaps.

---

## 📚 API Endpoints

### Health Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health/` | GET | Health check |
| `/api/health/version` | GET | Get application version |

### Pipeline Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipelines/embed` | PUT | Start embedding pipeline |

### Data Source Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/data_sources/data.sources.get` | GET | List data sources |
| `/api/data_sources/data.sources.create` | POST | Create data source |
| `/api/data_sources/data.sources.delete` | DELETE | Delete data source |

### Document Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/docs/upload` | POST | Upload documents |
| `/api/docs/list` | GET | List uploaded documents |
| `/api/docs/delete` | DELETE | Delete document |

### Slack Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/slack/channels.list` | GET | List Slack channels |
| `/api/slack/messages.fetch` | POST | Fetch channel messages |

For detailed API documentation, see [ARCHITECTURE.md - API Layer](./ARCHITECTURE.md#api-layer).

---

## 🔄 Common Workflows

### Workflow 1: Process Documents

```
📄 Upload documents → Process through pipeline → Store in vector DB
```

1. Upload documents via `/api/docs/upload`
2. Backend registers documents in MongoDB
3. Celery worker picks up task from `docs_queue`
4. Pipeline processes: Extract → Transform → Chunk → Embed → Load
5. Embeddings stored in Qdrant for retrieval

### Workflow 2: Index Slack Channels

```
💬 Connect Slack → Fetch messages → Embed conversations → Enable search
```

1. Configure Slack tokens in environment
2. List channels via `/api/slack/channels.list`
3. Trigger indexing via `/api/pipelines/embed`
4. Celery worker processes messages from `slack_queue`
5. Conversations embedded and stored in Qdrant

### Workflow 3: Vector Search

```
🔍 Query → Search embeddings → Retrieve relevant chunks
```

1. Generate query embedding
2. Search Qdrant via `/api/vector/search`
3. Retrieve top-k similar chunks
4. Return results with metadata and source links

---

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t unifai-backend:latest .
```

### Run Container

```bash
docker run -d \
  --name unifai-backend \
  -p 13456:13456 \
  -e MONGODB_IP=mongo \
  -e QDRANT_IP=qdrant \
  -e RABBITMQ_IP=rabbitmq \
  -e FRONTEND_URL=http://localhost:5000 \
  --network unifai-network \
  unifai-backend:latest
```

### Docker Compose (Recommended)

Create a `docker-compose.yml` to run all services together:

```yaml
version: '3.8'

services:
  mongo:
    image: mongo:5.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  backend:
    build: .
    ports:
      - "13456:13456"
    environment:
      MONGODB_IP: mongo
      RABBITMQ_IP: rabbitmq
      QDRANT_IP: qdrant
      FRONTEND_URL: http://localhost:5000
    depends_on:
      - mongo
      - rabbitmq
      - qdrant

volumes:
  mongo_data:
  qdrant_data:
```

Run with:
```bash
docker-compose up -d
```

---

## 🐛 Troubleshooting

### Issue 1: Celery Worker Not Processing Tasks

**Symptom:** Tasks stay in pending state, workers appear idle

**Solutions:**
```bash
# Check RabbitMQ is running and accessible
curl http://localhost:15672/api/overview
# Login: guest/guest

# Check worker connectivity
celery -A celery_app.init inspect active

# Restart worker with debug logging
celery -A celery_app.init worker -Q docs_queue -n docs_worker --loglevel=debug

# Check queue status in RabbitMQ management UI
# http://localhost:15672/#/queues
```

### Issue 2: MongoDB Connection Failed

**Symptom:** `ConnectionError: Could not connect to MongoDB`

**Solutions:**
```bash
# Verify MongoDB is running
docker ps | grep mongo

# Test connection manually
mongosh --host localhost --port 27017

# Check MongoDB logs
docker logs mongo

# Verify network connectivity (in Docker environment)
docker network inspect unifai-network
```

### Issue 3: Qdrant Collection Not Found

**Symptom:** `CollectionNotFound: Collection 'documents' does not exist`

**Solution:**
```python
# Collections are auto-created by pipeline
# If manual creation needed:
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
client.create_collection(
    collection_name="documents",
    vectors_config={"size": 384, "distance": "Cosine"}
)
```

### Issue 4: File Upload Fails

**Symptom:** `FileNotFoundError` or permission denied

**Solutions:**
```bash
# Create upload directory with proper permissions
mkdir -p /app/shared/uploads
chmod 777 /app/shared/uploads

# Check Flask configuration
python -c "from config.app_config import AppConfig; print(AppConfig.get_instance().upload_folder)"

# Verify disk space
df -h
```

### Issue 5: Import Errors for global_utils

**Symptom:** `ModuleNotFoundError: No module named 'global_utils'`

**Solution:**
```bash
# Install global_utils in development mode
cd ../global_utils
pip install -e .

# Or from backend directory
pip install -e ../global_utils/

# Verify installation
pip list | grep global-utils
```

### Issue 6: Pipeline Execution Timeout

**Symptom:** Celery task times out on large documents

**Solution:**
```python
# Increase task timeout in celery_app/init.py
celery_app.conf.update(
    task_time_limit=3600,      # 1 hour hard limit
    task_soft_time_limit=3000  # 50 minutes soft limit
)

# Or set per-task
@celery_app.task(time_limit=7200)
def process_large_document(source_id: str):
    pass
```

For detailed troubleshooting, see [ARCHITECTURE.md - Troubleshooting](./ARCHITECTURE.md#troubleshooting).

---

## 📝 Development Guidelines

### Code Style

- Follow **PEP 8** Python style guide
- Use **type hints** for function signatures
- Provide **docstrings** (Google style) for all functions
- Organize imports: stdlib → third-party → local

### Testing

```bash
# Run unit tests (if available)
pytest tests/

# Run with coverage
pytest --cov=. tests/

# Run specific test file
pytest tests/test_pipeline.py
```

### Adding New Data Sources

1. Create connector in `data_sources/<source_name>/`
2. Implement pipeline in `pipeline/<source_name>_pipeline.py`
3. Create factory in `pipeline/<source_name>_pipeline_factory.py`
4. Register in `pipeline/pipeline_factory.py`
5. Create Celery task in `celery_app/tasks/<source_name>_tasks.py`
6. Add API endpoints in `endpoints/<source_name>.py`

For detailed conventions, see [ARCHITECTURE.md - Code Conventions](./ARCHITECTURE.md#code-conventions).

---

## 📚 Additional Resources

### Documentation
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Comprehensive technical documentation including:
  - Detailed architecture patterns
  - RAG pipeline system explanation
  - Code conventions and best practices
  - API layer documentation
  - Storage and persistence patterns
  - Complete troubleshooting guide

### Related Documentation
- [UI README](../ui/README.md) - Frontend setup and development
- [Multi-Agent Backend](../multi-agent/README.md) - Agentic AI backend
- [Helm Deployment Guide](../helm/README.md) - Kubernetes deployment
- [CI/CD Pipelines](../ci/README.md) - Build and deployment pipelines

### Technology Documentation
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [LangChain Documentation](https://python.langchain.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [MongoDB Documentation](https://www.mongodb.com/docs/)

---

## 🤝 Contributing

When contributing to the backend:

1. **Create a feature branch** from `main`
2. **Follow code conventions** (see ARCHITECTURE.md)
3. **Add tests** for new functionality
4. **Update documentation** (README.md and ARCHITECTURE.md)
5. **Test locally** with all services running
6. **Create pull request** with clear description

### Code Review Checklist

- [ ] Code follows PEP 8 style guide
- [ ] Type hints provided for functions
- [ ] Docstrings added (Google style)
- [ ] Error handling implemented
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Local testing passed
- [ ] No hardcoded credentials or secrets

---

## ⚙️ Important Files

| File | Purpose |
|------|---------|
| `app.py` | Flask application entry point |
| `requirements.txt` | Python dependencies |
| `config/app_config.py` | Application configuration |
| `endpoints/__init__.py` | API blueprint registration |
| `pipeline/pipeline.py` | Base pipeline interface |
| `celery_app/init.py` | Celery configuration |
| `Dockerfile` | Container build instructions |
| `entrypoint.sh` | Container startup script |

---

## 🎯 Quick Start Checklist

- [ ] Install Python 3.x
- [ ] Start MongoDB container
- [ ] Start RabbitMQ container
- [ ] Start Qdrant container
- [ ] Create virtual environment
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Install global_utils (`pip install -e ../global_utils/`)
- [ ] Configure environment variables (optional)
- [ ] Run Flask app (`python app.py`)
- [ ] Start Celery workers (2 terminals)
- [ ] Test health endpoint: `curl http://localhost:13456/api/health/`
- [ ] Verify services in RabbitMQ management UI

---

**Happy Coding! 🚀**

For questions or issues, refer to [ARCHITECTURE.md](./ARCHITECTURE.md) or reach out to the UnifAI development team.

