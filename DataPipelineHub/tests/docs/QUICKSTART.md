# Quick Start Guide - Document Upload Stress Test

## 5-Minute Setup and Run

### 1. Install Dependencies
```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/tests/docs
pip install -r requirements_stress_test.txt
```

### 2. Verify Services are Running

**Check Backend:**
```bash
curl http://localhost:13457/api/health
# Should return: {"status": "ok", "message": "Server is healthy"}
```

**Check MongoDB:**
```bash
mongosh --eval "db.adminCommand('ping')"
# Should return: { ok: 1 }
```

**Check Celery Workers:**
```bash
# In the backend directory
celery -A celery_app inspect active
# Should show active workers
```

### 3. Run the Test

**Option A: Using the Runner Script (Recommended)**
```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/tests/docs
./run_stress_test.sh
```

**Option B: Direct Python Execution**
```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/tests/docs
python3 stress_test_doc_upload.py
```

### 4. Monitor Progress

The test will display real-time progress in the console:
- ✓ Green checkmarks = success
- ✗ Red X marks = failures
- Progress bars and statistics

### 5. Review Results

After completion, check:
1. **Console output** - Final report with all statistics
2. **Log file** - Detailed logs saved as `stress_test_YYYYMMDD_HHMMSS.log`

**Analyze logs:**
```bash
python3 analyze_stress_test_logs.py stress_test_*.log
```

## Expected Results

### Success Criteria
- ✓ Upload success rate: ≥95%
- ✓ All Celery tasks: SUCCESS status
- ✓ No timeouts or critical errors

### Typical Duration
- **Local development**: 15-20 minutes
- **Production environment**: 8-12 minutes

## Troubleshooting Quick Fixes

### Backend Not Running
```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/backend
python app.py
```

### Celery Workers Not Running
```bash
cd ${CURRENT_PATH}/unifai/DataPipelineHub/backend
celery -A celery_app worker --loglevel=info -Q docs_queue
```

### MongoDB Not Running
```bash
sudo systemctl start mongod
```

### RabbitMQ Not Running
```bash
sudo systemctl start rabbitmq-server
```

## Configuration Options

### Default Settings
- Documents: 100
- Pages per document: 2
- Concurrent uploads: 10
- API: http://localhost:13457/api
- MongoDB: localhost:27017

### Custom Configuration
Edit `StressTestConfig` class in `stress_test_doc_upload.py`:

```python
class StressTestConfig:
    NUM_DOCUMENTS = 50  # Change to 50 documents
    CONCURRENT_UPLOADS = 5  # Reduce concurrent uploads
```

Or use environment variables:
```bash
export API_BASE_URL="http://192.168.1.100:13457/api"
export MONGODB_HOST="mongodb.example.com"
./run_stress_test.sh
```

## What the Test Does

1. **Generate PDFs**: Creates 100 unique 2-page PDF documents
2. **Upload**: Sends all PDFs to backend API concurrently
3. **Track Uploads**: Monitors success/failure of each upload
4. **Trigger Pipeline**: Initiates embedding pipeline for all documents
5. **Monitor Tasks**: Watches Celery tasks until completion
6. **Generate Report**: Produces detailed statistics and assessment

## Understanding the Output

### Upload Phase
```
✓ Document 1 (stress_test_doc_001.pdf) uploaded successfully in 2.34s
✓ Document 2 (stress_test_doc_002.pdf) uploaded successfully in 2.45s
Progress: 100/100 successful, 0 failed
```

### Embedding Phase
```
✓ Task abc123... completed successfully
✓ Task def456... completed successfully
```

### Final Report
```
>>> UPLOAD PHASE SUMMARY <<<
Total upload attempts: 100
Successful uploads: 100
Failed uploads: 0
Success rate: 100.00%
Average upload time: 2.45s

>>> EMBEDDING PHASE SUMMARY <<<
Successful tasks: 100
Failed tasks: 0

>>> OVERALL ASSESSMENT <<<
✓ STRESS TEST PASSED
```

## Cleanup After Test

```bash
# Remove uploaded test files
rm /app/shared/stress_test_doc_*.pdf

# Remove test logs (optional)
rm stress_test_*.log
```

## Need Help?

1. **Check logs first**: Look at the generated log file for details
2. **Analyze logs**: Use `analyze_stress_test_logs.py` for insights
3. **Review docs**: See [README.md](README.md) for comprehensive documentation
4. **Check services**: Ensure all services (backend, MongoDB, Celery, RabbitMQ) are running

## Advanced Usage

### Run with Pre-flight Checks Only
```bash
./run_stress_test.sh --check-only
```

### Run with Custom Settings
```bash
./run_stress_test.sh \
  --api-url http://api.example.com:13457/api \
  --mongo-host mongodb.example.com
```

### Export Analysis to JSON
```bash
python3 analyze_stress_test_logs.py stress_test_*.log --export-json results.json
```

## Performance Tips

For slower systems:
- Reduce `NUM_DOCUMENTS` to 25 or 50
- Reduce `CONCURRENT_UPLOADS` to 3 or 5
- Increase `UPLOAD_TIMEOUT` to 600

For faster systems:
- Increase `CONCURRENT_UPLOADS` to 20
- Test with more documents (200+)

---

For complete documentation, see [README.md](README.md)  
For command reference, see [QUICK_REFERENCE.txt](QUICK_REFERENCE.txt)
