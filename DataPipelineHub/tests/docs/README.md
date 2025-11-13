# 🧪 Document Upload Stress Test Suite

> Complete guide for stress testing document upload and embedding pipelines

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Status: Production Ready](https://img.shields.io/badge/status-production%20ready-success.svg)]()

---

## 📋 Table of Contents

1. [Quick Start](#-quick-start)
2. [Overview](#-overview)
3. [What This Test Does](#-what-this-test-does)
4. [Installation](#-installation)
5. [Configuration](#-configuration)
6. [Running the Test](#-running-the-test)
7. [Understanding Results](#-understanding-results)
8. [Architecture](#-architecture)
9. [Technical Implementation](#-technical-implementation)
10. [Troubleshooting](#-troubleshooting)
11. [Advanced Usage](#-advanced-usage)

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements_stress_test.txt

# 2. Verify setup
python3 verify_setup.py

# 3. Run test
./run_stress_test.sh
```

**That's it!** The test will run automatically and generate a detailed report.

For more details, see [QUICKSTART.md](QUICKSTART.md) or [QUICK_REFERENCE.txt](QUICK_REFERENCE.txt).

---

## 📋 Overview

### Purpose

This stress test suite validates the document upload and embedding pipeline's ability to handle high-volume concurrent operations. It simulates real-world load conditions to ensure system reliability and performance.

### Test Objectives

**Primary Goals:**
1. **Upload Resilience**: Verify system handles 100 concurrent document uploads
2. **Celery Task Management**: Ensure all embedding tasks complete successfully
3. **Vector Storage**: Validate embeddings are properly stored in vector DB
4. **Performance Benchmarking**: Measure average processing times
5. **Error Handling**: Identify system breaking points and error patterns

**Success Criteria:**
- ✅ Upload success rate ≥ 95%
- ✅ Zero Celery task failures
- ✅ Average upload time < 5 seconds
- ✅ All documents embedded and searchable
- ✅ No system crashes or timeouts

---

## 📊 What This Test Does

### Test Phases

```
┌─────────────────────────────────────────────────────┐
│  PHASE 1: DOCUMENT GENERATION                       │
│  • Creates 100 unique 2-page PDFs                   │
│  • Each document has unique content                 │
│  • Prevents duplicate detection                     │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 2: CONCURRENT UPLOAD                         │
│  • Uploads 100 documents in parallel                │
│  • Configurable concurrency (default: 10)           │
│  • Tracks success/failure rates                     │
│  • Measures upload times                            │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 3: PIPELINE TRIGGER                          │
│  • Initiates embedding pipeline                     │
│  • Submits all documents to Celery                  │
│  • Starts parallel processing                       │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 4: TASK MONITORING                           │
│  • Monitors Celery task execution                   │
│  • Tracks SUCCESS/FAILURE status                    │
│  • Waits for completion                             │
│  • Validates vector DB storage                      │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  PHASE 5: REPORT GENERATION                         │
│  • Calculates comprehensive statistics              │
│  • Identifies bottlenecks                           │
│  • Generates final assessment                       │
│  • Provides recommendations                         │
└─────────────────────────────────────────────────────┘
```

### Metrics Tracked

**Upload Phase:**
- Total upload attempts
- Success/failure counts
- Success rate percentage
- Average/Min/Max upload time
- 95th/99th percentile times
- Error categorization by type
- Throughput (docs/second)

**Embedding Phase:**
- Total Celery tasks
- Successful/Failed tasks
- Pending tasks
- Average task duration
- Task status breakdown
- Total processing time

**System Metrics:**
- Total test duration
- Concurrent connections
- API response times
- Error patterns and frequency

---

## 📁 Suite Components

### Test Scripts

| File | Purpose | Lines |
|------|---------|-------|
| `stress_test_doc_upload.py` | Main test script | 900+ |
| `run_stress_test.sh` | Test runner with checks | 250+ |
| `analyze_stress_test_logs.py` | Log analysis tool | 350+ |
| `verify_setup.py` | Pre-flight verification | 250+ |

### Supporting Files

| File | Purpose |
|------|---------|
| `requirements_stress_test.txt` | Python dependencies |
| `README.md` | This comprehensive guide |
| `QUICKSTART.md` | 5-minute setup guide |
| `QUICK_REFERENCE.txt` | Command reference card |

---

## 🔧 Installation

### Prerequisites

1. **Backend API** running (default: http://localhost:13457)
2. **MongoDB** accessible (default: localhost:27017)
3. **Celery workers** running
4. **RabbitMQ** running
5. **Vector DB (Qdrant)** accessible

### Install Dependencies

```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/tests/docs
pip install -r requirements_stress_test.txt
```

**Required packages:**
- `aiohttp>=3.9.0` - Async HTTP client
- `pymongo>=4.6.0` - MongoDB driver
- `reportlab>=4.0.0` - PDF generation

---

## ⚙️ Configuration

### Environment Variables

```bash
# API Configuration
export API_BASE_URL="http://localhost:13457/api"

# MongoDB Configuration
export MONGODB_HOST="localhost"
export MONGODB_PORT="27017"
export MONGODB_DB="celery"
```

### Code Configuration

Edit `StressTestConfig` in `stress_test_doc_upload.py`:

```python
class StressTestConfig:
    NUM_DOCUMENTS = 100              # Number of documents to generate
    CONCURRENT_UPLOADS = 10          # Simultaneous uploads
    PAGES_PER_DOC = 2                # Pages per PDF
    UPLOAD_TIMEOUT = 300             # Upload timeout (seconds)
    CELERY_MONITOR_TIMEOUT = 1800    # Task monitoring timeout (seconds)
    CELERY_POLL_INTERVAL = 5         # Poll interval (seconds)
```

### Script Options

```bash
./run_stress_test.sh --help                    # Show help
./run_stress_test.sh --check-only              # Verify setup only
./run_stress_test.sh --api-url URL             # Custom API URL
./run_stress_test.sh --mongo-host HOST         # Custom MongoDB host
./run_stress_test.sh --mongo-port PORT         # Custom MongoDB port
```

---

## ▶️ Running the Test

### Option 1: Using Runner Script (Recommended)

```bash
./run_stress_test.sh
```

This will:
- Check dependencies
- Verify service availability
- Run the stress test
- Generate detailed logs

### Option 2: Direct Execution

```bash
python3 stress_test_doc_upload.py
```

### Option 3: Verify Setup Only

```bash
python3 verify_setup.py
# or
./run_stress_test.sh --check-only
```

---

## 📊 Understanding Results

### Example Output

```
================================================================================
DOCUMENT UPLOAD STRESS TEST
================================================================================
Test started at: 2024-11-10T15:30:00
Configuration:
  - Number of documents: 100
  - Pages per document: 2
  - Concurrent uploads: 10
  - API endpoint: http://localhost:13457/api/docs/upload
================================================================================

================================================================================
PHASE 1: DOCUMENT UPLOAD
================================================================================
✓ Generated 100 unique PDF documents
Starting uploads with 10 concurrent connections...

--- Uploading Batch 1/10 ---
✓ Document 1 (stress_test_doc_001.pdf) uploaded successfully in 2.34s
✓ Document 2 (stress_test_doc_002.pdf) uploaded successfully in 2.45s
...
Progress: 100/100 successful, 0 failed

================================================================================
PHASE 2: MONITORING CELERY TASKS
================================================================================
✓ Task abc123... completed successfully
...
✓ All Celery tasks completed!

================================================================================
STRESS TEST FINAL REPORT
================================================================================

>>> UPLOAD PHASE SUMMARY <<<
Total upload attempts: 100
Successful uploads: 100
Failed uploads: 0
Success rate: 100.00%
Average upload time: 2.45s
Min upload time: 1.89s
Max upload time: 4.23s
Total upload duration: 45.67s

>>> EMBEDDING PHASE SUMMARY <<<
Successful tasks: 100
Failed tasks: 0
Pending tasks: 0
Average task duration: 12.34s
Total monitoring duration: 180.45s

>>> OVERALL ASSESSMENT <<<
✓ STRESS TEST PASSED
  System successfully handled 100 concurrent document uploads and embeddings

================================================================================
Test ended at: 2024-11-10T15:48:23
Total test duration: 1103.45s (18.39 minutes)
```

### Interpreting Results

**Upload Phase:**
- **Success Rate**: Should be ≥95%
- **Average Time**: Should be <5 seconds per document
- **Failed Uploads**: Check error types in the detailed breakdown

**Embedding Phase:**
- **Successful Tasks**: Should equal number of uploaded documents
- **Failed Tasks**: Should be 0
- **Pending Tasks**: Should be 0 at test completion

**Overall Assessment:**
- **PASSED**: System handled load successfully
- **FAILED**: Review specific metrics and error messages

### Log Files

After running, you'll find:
- **Console output**: Real-time progress
- **Log file**: `stress_test_YYYYMMDD_HHMMSS.log` with complete details

### Analyzing Logs

```bash
# Detailed analysis
python3 analyze_stress_test_logs.py stress_test_20241110_153045.log

# Export to JSON
python3 analyze_stress_test_logs.py stress_test_*.log --export-json results.json

# Compare test runs
diff results_baseline.json results_current.json
```

---

## 🏗️ Architecture

### System Integration

The test suite integrates with multiple components:

```
┌─────────────┐
│ Test Script │
└──────┬──────┘
       │
       ├──> Frontend Mimicry (UploadTab.tsx behavior)
       │    └─> Base64 encoding
       │    └─> API calls
       │
       ├──> Backend API (docs.py)
       │    └─> /api/docs/upload endpoint
       │    └─> File validation
       │    └─> Storage operations
       │
       ├──> RabbitMQ
       │    └─> Task queue management
       │
       ├──> Celery Workers
       │    └─> Document processing
       │    └─> Docling integration
       │    └─> Embedding generation
       │
       ├──> MongoDB
       │    └─> Task status storage
       │    └─> Pipeline tracking
       │
       └──> Vector DB (Qdrant)
            └─> Embedding storage
            └─> Search functionality
```

### Test Workflow

```
1. INITIALIZATION
   ├── Load configuration
   ├── Connect to MongoDB
   └── Verify API availability

2. PDF GENERATION
   ├── Generate 100 unique PDF documents
   │   ├── 2 pages per document
   │   ├── Unique content per document
   │   └── Random identifiers to prevent duplicates
   └── Store in memory

3. UPLOAD PHASE
   ├── Create concurrent upload tasks
   │   ├── Convert PDFs to base64
   │   ├── Send to /api/docs/upload
   │   └── Track timing and status
   ├── Process in batches (default: 10 concurrent)
   └── Record success/failure metrics

4. PIPELINE TRIGGER
   ├── Call /api/pipelines/embed
   ├── Submit all document names
   └── Initiate Celery workers

5. MONITORING PHASE
   ├── Poll MongoDB for task status
   ├── Track SUCCESS/FAILURE/PENDING states
   ├── Monitor until all tasks complete
   └── Calculate task durations

6. REPORTING
   ├── Generate upload statistics
   ├── Compile task metrics
   ├── Create final assessment
   └── Save detailed logs

7. CLEANUP
   └── Close MongoDB connections
```

---

## 🔬 Technical Implementation

### Document Generation

**Technology**: ReportLab PDF library

**Uniqueness Strategy:**
- Random unique identifiers (16 characters)
- Timestamps with millisecond precision
- Random topics from 25 different subjects
- Random data sections (200+ characters each)
- Ensures no duplicate content or base64 hashes

**Implementation:**
```python
def generate_unique_content(doc_id: int) -> str:
    topic = random.choice(TOPICS)
    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    timestamp = time.time()
    # ... generates 2-page PDF with unique content
```

### Concurrent Upload Implementation

**Technology**: aiohttp (async HTTP client)

**Method**:
- Batch processing with configurable concurrency
- Default: 10 simultaneous uploads
- Each upload timeout: 300 seconds
- Individual failures don't stop the test

**Implementation:**
```python
async def upload_batch(session, batch):
    tasks = [upload_single_document(session, doc) for doc in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Celery Task Monitoring

**Technology**: MongoDB backend for Celery

**Strategy**:
- Polls `celery_taskmeta` collection every 5 seconds
- Tracks task state transitions: PENDING → STARTED → SUCCESS/FAILURE
- Maximum monitoring time: 30 minutes
- Identifies completed, failed, and stuck tasks

**Implementation:**
```python
def monitor_celery_tasks(start_timestamp):
    while time.time() < timeout:
        tasks = celery_db.celery_taskmeta.find({'date_done': {'$gte': start_timestamp}})
        # Track status and update statistics
```

### Statistics Calculation

**Metrics Computed:**
- **Upload times**: Average, median, min, max, 95th/99th percentiles
- **Success rate**: (successful uploads / total uploads) × 100
- **Error categorization**: By HTTP status code, timeout, unknown
- **Task durations**: Per-task and aggregate statistics

---

## 📈 Performance Benchmarks

### Local Development
**Specs**: 8GB RAM, 4 CPU cores

| Metric | Expected |
|--------|----------|
| Upload time/doc | 3-5 seconds |
| Embedding time/doc | 15-20 seconds |
| Total duration | 15-20 minutes |
| Success rate | >95% |

### Production
**Specs**: 16GB RAM, 8 CPU cores

| Metric | Expected |
|--------|----------|
| Upload time/doc | 1-2 seconds |
| Embedding time/doc | 8-10 seconds |
| Total duration | 8-12 minutes |
| Success rate | >99% |

---

## 🔧 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Backend not responding | API not running | `cd backend && python app.py` |
| MongoDB connection failed | MongoDB not running | `sudo systemctl start mongod` |
| Celery tasks stuck in PENDING | Workers not running | `celery -A celery_app inspect active` |
| Upload timeouts | Slow network/overloaded backend | Reduce `CONCURRENT_UPLOADS` to 5 |
| Package import errors | Missing dependencies | `pip install -r requirements_stress_test.txt` |
| Permission denied | Scripts not executable | `chmod +x *.sh *.py` |
| Duplicate rejection | Content not unique | Clear test docs: `rm /app/shared/stress_test_doc_*.pdf` |

### Detailed Troubleshooting

#### Connection Refused
**Symptoms**: Cannot connect to backend API

**Solution**:
```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/backend
python app.py
```

#### Tasks Stuck in PENDING
**Symptoms**: Celery tasks not progressing

**Diagnosis**:
```bash
# Check workers
celery -A celery_app inspect active

# Check RabbitMQ
sudo systemctl status rabbitmq-server

# Check queue
celery -A celery_app inspect scheduled
```

**Solution**:
```bash
# Start workers
celery -A celery_app worker --loglevel=info -Q docs_queue

# Restart RabbitMQ if needed
sudo systemctl restart rabbitmq-server
```

#### Upload Timeouts
**Symptoms**: Multiple timeout errors during upload

**Solutions**:
1. Increase timeout: Edit `UPLOAD_TIMEOUT = 600` in config
2. Reduce concurrency: Edit `CONCURRENT_UPLOADS = 5`
3. Check backend logs: `tail -f /path/to/backend/logs/app.log`

### Service Health Checks

```bash
# Backend API
curl http://localhost:13457/api/health

# MongoDB
mongosh --eval "db.adminCommand('ping')"

# Celery workers
cd /path/to/backend && celery -A celery_app inspect active

# RabbitMQ
sudo rabbitmqctl status

# Qdrant
curl http://localhost:6333/dashboard
```

---

## 🧰 Advanced Usage

### Custom Test Scenarios

#### Scenario 1: Reduced Load Test (Faster)
```python
# Edit stress_test_doc_upload.py
class StressTestConfig:
    NUM_DOCUMENTS = 50           # Reduced from 100
    CONCURRENT_UPLOADS = 5       # Lower concurrency
```

#### Scenario 2: High Concurrency Test
```python
class StressTestConfig:
    NUM_DOCUMENTS = 100
    CONCURRENT_UPLOADS = 20      # Higher concurrency
```

#### Scenario 3: Volume Test
```python
class StressTestConfig:
    NUM_DOCUMENTS = 500          # Higher volume
    CONCURRENT_UPLOADS = 10
```

#### Scenario 4: Large Documents
```python
class StressTestConfig:
    PAGES_PER_DOC = 10          # More pages per document
```

### Testing Against Different Environments

```bash
# Staging environment
export API_BASE_URL="http://staging.api.example.com/api"
./run_stress_test.sh

# Production (use with caution!)
export API_BASE_URL="http://prod.api.example.com/api"
./run_stress_test.sh
```

### CI/CD Integration

```bash
#!/bin/bash
# ci_test.sh

export API_BASE_URL="http://staging-api:13457/api"
export MONGODB_HOST="staging-mongo"

python3 stress_test_doc_upload.py

if [ $? -eq 0 ]; then
    echo "✓ Stress test PASSED"
    exit 0
else
    echo "✗ Stress test FAILED"
    # Upload logs to artifact storage
    exit 1
fi
```

### Monitoring During Tests

Open multiple terminals to monitor different aspects:

**Terminal 1: Run test**
```bash
./run_stress_test.sh
```

**Terminal 2: Backend logs**
```bash
tail -f /path/to/backend/app.log
```

**Terminal 3: Celery events**
```bash
celery -A celery_app events
```

**Terminal 4: MongoDB monitoring**
```bash
watch -n 1 'mongosh celery --eval "db.celery_taskmeta.count()"'
```

**Terminal 5: RabbitMQ queue**
```bash
watch -n 1 'rabbitmqctl list_queues'
```

### Performance Analysis

```bash
# Run test
./run_stress_test.sh

# Analyze results
python3 analyze_stress_test_logs.py stress_test_*.log --export-json results.json

# Compare with baseline
diff baseline.json results.json

# Track over time
echo "$(date),$(jq '.statistics.upload_avg' results.json)" >> performance_history.csv
```

### Cleanup After Testing

```bash
# Remove uploaded test files
rm /app/shared/stress_test_doc_*.pdf

# Remove old log files (keep last 5)
ls -t stress_test_*.log | tail -n +6 | xargs rm

# Clear test data from MongoDB (optional)
mongosh celery --eval "db.celery_taskmeta.deleteMany({task: /stress_test/})"
```

---

## 📞 Support and Maintenance

### Getting Help

1. **Run verification**: `python3 verify_setup.py`
2. **Check logs**: Review `stress_test_*.log` file
3. **Analyze results**: `python3 analyze_stress_test_logs.py <logfile>`
4. **Review this guide**: See troubleshooting section above
5. **Contact team**: Reach out to DevOps team

### Regular Maintenance

- **Weekly**: Review test logs for patterns
- **Monthly**: Update dependencies (`pip install -U -r requirements_stress_test.txt`)
- **Quarterly**: Benchmark performance trends
- **As needed**: Update for API changes

### Extending the Suite

The code is structured for easy extension:
- Add new document types (DOCX, TXT, etc.)
- Implement additional metrics
- Add real-time dashboards
- Integrate with monitoring tools (Grafana, Prometheus)
- Add distributed testing support (multiple test clients)

### Future Enhancements

Planned features:
- [ ] Real-time monitoring dashboard
- [ ] Distributed load generation
- [ ] Performance regression testing
- [ ] Automated CI/CD integration
- [ ] Network latency simulation
- [ ] Memory and CPU profiling
- [ ] WebSocket support testing

---

## 📄 License and Attribution

Part of UnifAI DataPipelineHub project.  
For internal use only.

**Version**: 1.0.0  
**Last Updated**: November 2024  
**Maintainer**: Software Engineering Team

---

## ⭐ Quick Reference

For quick commands and setup, see:
- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[QUICK_REFERENCE.txt](QUICK_REFERENCE.txt)** - Command reference card

---

**Ready to test?** Run `./run_stress_test.sh` and start stress testing your system! 🚀
