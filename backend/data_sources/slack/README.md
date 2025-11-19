# Slack Retreival Flow
1. User send request for processing certain slack channenls. 
2. For each channel from user list, celery task is allocated, each task run on specific worker. (task responsible on all the layers, starting from the Data Collection layer till the Chunking layer) 
3. Task tagged with metadata pinpoining to the 'Slack' data_source.
4. 'Thread_messages' retreival handled by separated API requests managed within a dedicated 'Thread Pool'. 

--------------------------------------------------------------------------------------------------------------------------------------------

# Challenges & Thoughts

Handling heavy synchronous backend operations under concurrency pressure (might happen once user start the 'Slack Pipeline' for few channels altogether:

### 🔹 Option 1: Stay synchronous but control concurrency
Using a thread pool (like concurrent.futures.ThreadPoolExecutor) and limit max workers.
Don’t spawn infinite threads — control queue depth.
Return a “job is being processed” response and let the client poll or subscribe (see async note below).

```python
executor = ThreadPoolExecutor(max_workers=10)  # reasonable limit
future = executor.submit(heavy_api_call, ...)
```

### 🔹  Option 2: Scaling Recommendations (Large Scale)
✅ Kubernetes-based Scaling
Horizontal Pod Autoscaling (HPA): scale pods based on CPU usage or custom metrics (like queue length).

✅ Use a Message Broker for Heavy Async Work
When scale increases or operations get more complex/time-consuming, you should consider offloading work to a queue.

Pattern:
1. Main API receives the request → queues a job (e.g., in Redis, RabbitMQ, or Kafka) → returns 202 Accepted.
2. A background worker service (Celery, custom Python thread, etc.) picks up the job and processes it.
3. Client can poll or be notified via webhook or websocket.

Benefits:
1. Prevents overloading your HTTP server.
2. You can scale worker pods separately.
3. More robust under load, and failures can be retried or logged.
