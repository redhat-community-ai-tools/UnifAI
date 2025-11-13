"""
Document Upload Stress Test
=============================
This stress test validates the system's ability to handle concurrent document uploads
and embedding pipeline execution under load.

Test Scope:
-----------
1. Upload Phase: Tests concurrent upload of 100 unique PDF documents
2. Embedding Phase: Monitors Celery task execution for document embedding
3. Vector Storage Phase: Validates successful vector storage in DB
"""

import asyncio
import aiohttp
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import pymongo
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from io import BytesIO
import random
import string

# Configure logging
log_level = logging.DEBUG if os.getenv("DEBUG", "").lower() in ["1", "true", "yes"] else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'stress_test_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging level set to: {logging.getLevelName(log_level)}")


class StressTestConfig:
    """Configuration for stress test"""
    # API Configuration
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:13457/api")
    UPLOAD_ENDPOINT = f"{API_BASE_URL}/docs/upload"
    EMBED_ENDPOINT = f"{API_BASE_URL}/pipelines/embed"
    
    # MongoDB Configuration
    MONGODB_HOST = os.getenv("MONGODB_HOST", "0.0.0.0")
    MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
    MONGODB_DB = os.getenv("MONGODB_DB", "celery")
    
    # Test Configuration
    NUM_DOCUMENTS = 100
    CONCURRENT_UPLOADS = 10  # Number of simultaneous uploads
    PAGES_PER_DOC = 2
    
    # Timeout Configuration
    UPLOAD_TIMEOUT = 300  # 5 minutes per upload
    CELERY_MONITOR_TIMEOUT = 1800  # 30 minutes for all celery tasks
    CELERY_POLL_INTERVAL = 5  # Poll every 5 seconds
    
    # User Configuration
    TEST_USER = "stress_test_user"


class DocumentGenerator:
    """Generates unique PDF documents for testing"""
    
    TOPICS = [
        "Artificial Intelligence", "Machine Learning", "Deep Learning",
        "Cloud Computing", "Blockchain Technology", "Quantum Computing",
        "Cybersecurity", "Internet of Things", "Big Data Analytics",
        "Natural Language Processing", "Computer Vision", "Robotics",
        "Edge Computing", "5G Networks", "Augmented Reality",
        "Virtual Reality", "DevOps", "Microservices", "Kubernetes",
        "Docker Containers", "Serverless Computing", "API Design",
        "Database Management", "Data Warehousing", "ETL Processes"
    ]
    
    @staticmethod
    def generate_unique_content(doc_id: int) -> str:
        """Generate unique content for each document"""
        topic = random.choice(DocumentGenerator.TOPICS)
        unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        
        content = f"""
        Document ID: {doc_id}
        Unique Identifier: {unique_id}
        Topic: {topic}
        Generated: {datetime.now().isoformat()}
        
        Introduction to {topic}
        {'=' * 50}
        
        This document discusses the fundamentals and advanced concepts of {topic}.
        Each document in this stress test contains unique content to ensure proper
        handling of distinct documents by the system.
        
        Section 1: Overview
        {'-' * 30}
        {topic} represents a significant advancement in modern technology.
        Random data: {random.random()}
        Timestamp: {time.time()}
        
        """
        
        # Add more unique paragraphs
        for i in range(5):
            content += f"""
        Section {i+2}: Detailed Analysis Part {i+1}
        {'-' * 30}
        This section contains unique information about {topic} with random data:
        {' '.join(random.choices(string.ascii_letters, k=200))}
        
        Key Points:
        - Point 1: Random value {random.randint(1000, 9999)}
        - Point 2: Unique timestamp {time.time()}
        - Point 3: Random string {unique_id[:8]}
        
            """
        
        return content
    
    @staticmethod
    def create_pdf(doc_id: int, filename: str) -> bytes:
        """Create a 2-page PDF document with unique content"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
        )
        story.append(Paragraph(f"Stress Test Document #{doc_id}", title_style))
        story.append(Spacer(1, 0.2 * inch))
        
        # Generate unique content
        content = DocumentGenerator.generate_unique_content(doc_id)
        
        # Split content into two pages
        paragraphs = content.split('\n\n')
        mid_point = len(paragraphs) // 2
        
        # Page 1
        for para in paragraphs[:mid_point]:
            if para.strip():
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
        
        # Page break
        story.append(PageBreak())
        
        # Page 2
        story.append(Paragraph(f"Document #{doc_id} - Page 2", styles['Heading2']))
        story.append(Spacer(1, 0.2 * inch))
        for para in paragraphs[mid_point:]:
            if para.strip():
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
        
        # Footer with unique identifier
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(
            f"Unique ID: {time.time()}-{doc_id}-{random.randint(10000, 99999)}",
            styles['Normal']
        ))
        
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes


class CeleryMonitor:
    """Monitors Celery task execution"""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.mongo_client = None
        self.celery_db = None
        
    def connect(self):
        """Connect to MongoDB"""
        try:
            self.mongo_client = pymongo.MongoClient(
                self.config.MONGODB_HOST,
                self.config.MONGODB_PORT,
                serverSelectionTimeoutMS=5000
            )
            self.celery_db = self.mongo_client[self.config.MONGODB_DB]
            # Test connection
            self.mongo_client.server_info()
            logger.info(f"Connected to MongoDB at {self.config.MONGODB_HOST}:{self.config.MONGODB_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MongoDB"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_recent_tasks(self, since_timestamp: datetime) -> List[Dict]:
        """Get Celery tasks created after a specific timestamp
        
        Note: Celery stores date_done in UTC, so we ensure since_timestamp is also UTC
        for reliable comparison.
        """
        try:
            # Ensure we're working with UTC time for comparison with Celery's UTC timestamps
            if since_timestamp.tzinfo is None:
                # If naive datetime, assume it's UTC
                since_timestamp_utc = since_timestamp.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC if it has timezone info
                since_timestamp_utc = since_timestamp.astimezone(timezone.utc)
            
            logger.debug(f"Querying Celery tasks since {since_timestamp_utc.isoformat()}")
            
            collection = self.celery_db['celery_taskmeta']
            tasks = list(collection.find({
                'date_done': {'$gte': since_timestamp_utc}
            }))
            logger.debug(f"Found {len(tasks)} tasks since {since_timestamp_utc.isoformat()}")
            return tasks
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
            return []
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task"""
        try:
            collection = self.celery_db['celery_taskmeta']
            task = collection.find_one({'_id': task_id})
            return task
        except Exception as e:
            logger.error(f"Error fetching task {task_id}: {e}")
            return None
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict]:
        """Get pipeline status from pipelines collection"""
        try:
            # Try different common database names
            for db_name in ['unifai', 'datapipeline', 'backend', 'celery']:
                try:
                    db = self.mongo_client[db_name]
                    collection = db['pipelines']
                    pipeline = collection.find_one({'pipeline_id': pipeline_id})
                    if pipeline:
                        return pipeline
                except:
                    continue
            return None
        except Exception as e:
            logger.error(f"Error fetching pipeline {pipeline_id}: {e}")
            return None


class UploadStats:
    """Tracks upload statistics"""
    
    def __init__(self):
        self.successful_uploads = 0
        self.failed_uploads = 0
        self.upload_times = []
        self.errors = defaultdict(int)
        self.start_time = None
        self.end_time = None
    
    def record_success(self, duration: float):
        """Record successful upload"""
        self.successful_uploads += 1
        self.upload_times.append(duration)
    
    def record_failure(self, error: str):
        """Record failed upload"""
        self.failed_uploads += 1
        self.errors[error] += 1
    
    def get_summary(self) -> Dict:
        """Get statistics summary"""
        total_uploads = self.successful_uploads + self.failed_uploads
        avg_time = sum(self.upload_times) / len(self.upload_times) if self.upload_times else 0
        min_time = min(self.upload_times) if self.upload_times else 0
        max_time = max(self.upload_times) if self.upload_times else 0
        
        return {
            'total_attempts': total_uploads,
            'successful': self.successful_uploads,
            'failed': self.failed_uploads,
            'success_rate': (self.successful_uploads / total_uploads * 100) if total_uploads > 0 else 0,
            'avg_upload_time': avg_time,
            'min_upload_time': min_time,
            'max_upload_time': max_time,
            'total_duration': self.end_time - self.start_time if self.end_time and self.start_time else 0,
            'errors': dict(self.errors)
        }


class EmbeddingStats:
    """Tracks embedding/celery task statistics"""
    
    def __init__(self):
        self.successful_tasks = 0
        self.failed_tasks = 0
        self.pending_tasks = 0
        self.task_durations = []
        self.task_statuses = defaultdict(int)
        self.start_time = None
        self.end_time = None
    
    def update(self, status: str, duration: Optional[float] = None):
        """Update statistics"""
        self.task_statuses[status] += 1
        if status == 'SUCCESS':
            self.successful_tasks += 1
            if duration:
                self.task_durations.append(duration)
        elif status == 'FAILURE':
            self.failed_tasks += 1
        elif status in ['PENDING', 'STARTED']:
            self.pending_tasks += 1
    
    def get_summary(self) -> Dict:
        """Get statistics summary"""
        avg_duration = sum(self.task_durations) / len(self.task_durations) if self.task_durations else 0
        
        return {
            'successful_tasks': self.successful_tasks,
            'failed_tasks': self.failed_tasks,
            'pending_tasks': self.pending_tasks,
            'avg_task_duration': avg_duration,
            'total_monitoring_duration': self.end_time - self.start_time if self.end_time and self.start_time else 0,
            'status_breakdown': dict(self.task_statuses)
        }


class StressTestRunner:
    """Main stress test runner"""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.upload_stats = UploadStats()
        self.embedding_stats = EmbeddingStats()
        self.celery_monitor = CeleryMonitor(config)
        self.document_filenames = []
        self.pipeline_ids = []
        
    async def upload_single_document(
        self, 
        session: aiohttp.ClientSession,
        doc_id: int,
        filename: str,
        pdf_bytes: bytes
    ) -> Tuple[bool, float, Optional[str]]:
        """Upload a single document to the API"""
        start_time = time.time()
        
        try:
            # Convert to base64
            base64_content = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # Prepare payload
            payload = {
                'files': [
                    {
                        'name': filename,
                        'content': base64_content
                    }
                ]
            }
            
            # Make API call
            async with session.post(
                self.config.UPLOAD_ENDPOINT,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.UPLOAD_TIMEOUT)
            ) as response:
                duration = time.time() - start_time
                
                if response.status == 200:
                    logger.info(f"✓ Document {doc_id} ({filename}) uploaded successfully in {duration:.2f}s")
                    return True, duration, None
                else:
                    error_text = await response.text()
                    error_msg = f"HTTP {response.status}: {error_text}"
                    logger.error(f"✗ Document {doc_id} ({filename}) upload failed: {error_msg}")
                    return False, duration, error_msg
                    
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            error_msg = "Upload timeout"
            logger.error(f"✗ Document {doc_id} ({filename}) upload timeout after {duration:.2f}s")
            return False, duration, error_msg
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"✗ Document {doc_id} ({filename}) upload error: {error_msg}")
            return False, duration, error_msg
    
    async def upload_batch(
        self,
        session: aiohttp.ClientSession,
        batch: List[Tuple[int, str, bytes]]
    ):
        """Upload a batch of documents concurrently"""
        tasks = [
            self.upload_single_document(session, doc_id, filename, pdf_bytes)
            for doc_id, filename, pdf_bytes in batch
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                self.upload_stats.record_failure(str(result))
            else:
                success, duration, error = result
                if success:
                    self.upload_stats.record_success(duration)
                else:
                    self.upload_stats.record_failure(error or "Unknown error")
    
    async def trigger_embedding_pipeline(self, session: aiohttp.ClientSession):
        """Trigger the embedding pipeline for all uploaded documents"""
        try:
            logger.info(f"Triggering embedding pipeline for {len(self.document_filenames)} documents...")
            
            payload = {
                'data': [{'source_name': filename} for filename in self.document_filenames],
                'source_type': 'document',
                'logged_in_user': self.config.TEST_USER
            }
            
            async with session.put(
                self.config.EMBED_ENDPOINT,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status in [200, 202]:
                    response_data = await response.json()
                    logger.info(f"✓ Embedding pipeline triggered successfully")
                    logger.info(f"Response: {response_data}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to trigger embedding pipeline: HTTP {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Error triggering embedding pipeline: {e}")
            return False
    
    def monitor_celery_tasks(self, start_timestamp: datetime):
        """Monitor Celery tasks until completion or timeout"""
        logger.info("\n" + "="*80)
        logger.info("PHASE 2: MONITORING CELERY TASKS")
        logger.info("="*80)
        
        self.embedding_stats.start_time = time.time()
        timeout = time.time() + self.config.CELERY_MONITOR_TIMEOUT
        
        completed_tasks = set()
        last_log_time = time.time()
        
        while time.time() < timeout:
            try:
                # Get recent tasks
                tasks = self.celery_monitor.get_recent_tasks(start_timestamp)
                
                # Filter tasks related to document RAG process
                # Check if result.pipeline_id starts with 'document_' to identify relevant tasks
                relevant_tasks = []
                for task in tasks:
                    result = task.get('result', {})
                    if result:
                        # Handle both dict and JSON string results
                        if isinstance(result, str):
                            # Result is stored as JSON string, parse it
                            try:
                                result = json.loads(result)
                                logger.debug(f"Parsed JSON string result for task {task.get('_id', '')[:8]}")
                            except json.JSONDecodeError as e:
                                logger.debug(f"Failed to parse result JSON: {e}")
                                continue
                        
                        # Now result should be a dict
                        if isinstance(result, dict):
                            pipeline_id = result.get('pipeline_id', '')
                            
                            # Check if pipeline_id starts with 'document_'
                            if isinstance(pipeline_id, str) and pipeline_id.startswith('document_'):
                                relevant_tasks.append(task)
                                logger.debug(f"Found relevant task with pipeline_id: {pipeline_id}")
                        else:
                            logger.debug(f"Result is neither string nor dict: {type(result)}")
                
                logger.debug(f"Found {len(relevant_tasks)} relevant document RAG tasks out of {len(tasks)} total tasks")
                
                # Update statistics
                current_pending = 0
                current_success = 0
                current_failed = 0
                
                for task in relevant_tasks:
                    task_id = task.get('_id')
                    status = task.get('status', 'UNKNOWN')
                    
                    if task_id not in completed_tasks:
                        if status == 'SUCCESS':
                            completed_tasks.add(task_id)
                            date_done = task.get('date_done')
                            # Calculate duration if possible
                            duration = None
                            if date_done and 'date_start' in task:
                                duration = (date_done - task['date_start']).total_seconds()
                            self.embedding_stats.update('SUCCESS', duration)
                            logger.info(f"✓ Task {task_id[:8]}... completed successfully")
                        elif status == 'FAILURE':
                            completed_tasks.add(task_id)
                            self.embedding_stats.update('FAILURE')
                            result = task.get('result', {})
                            logger.error(f"✗ Task {task_id[:8]}... failed: {result}")
                    
                    # Count current statuses
                    if status == 'SUCCESS':
                        current_success += 1
                    elif status == 'FAILURE':
                        current_failed += 1
                    elif status in ['PENDING', 'STARTED']:
                        current_pending += 1
                
                # Log progress every 30 seconds
                if time.time() - last_log_time >= 30:
                    logger.info(f"\n--- Task Status Update ---")
                    logger.info(f"Total tasks found: {len(relevant_tasks)}")
                    logger.info(f"Success: {current_success}")
                    logger.info(f"Failed: {current_failed}")
                    logger.info(f"Pending/Started: {current_pending}")
                    logger.info(f"Monitoring time: {time.time() - self.embedding_stats.start_time:.0f}s")
                    last_log_time = time.time()
                
                # Check if all tasks are completed
                if len(relevant_tasks) >= self.config.NUM_DOCUMENTS:
                    all_completed = all(
                        task.get('status') in ['SUCCESS', 'FAILURE']
                        for task in relevant_tasks
                    )
                    if all_completed:
                        logger.info("\n✓ All Celery tasks completed!")
                        break
                
                # Wait before next poll
                time.sleep(self.config.CELERY_POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error monitoring tasks: {e}")
                time.sleep(self.config.CELERY_POLL_INTERVAL)
        
        self.embedding_stats.end_time = time.time()
        
        if time.time() >= timeout:
            logger.warning("⚠ Celery task monitoring timeout reached")
    
    async def run_upload_phase(self):
        """Run the document upload phase"""
        logger.info("\n" + "="*80)
        logger.info("PHASE 1: DOCUMENT UPLOAD")
        logger.info("="*80)
        logger.info(f"Generating and uploading {self.config.NUM_DOCUMENTS} documents...")
        logger.info(f"Concurrent uploads: {self.config.CONCURRENT_UPLOADS}")
        
        self.upload_stats.start_time = time.time()
        
        # Generate all documents first
        logger.info("Generating PDF documents...")
        documents = []
        for i in range(1, self.config.NUM_DOCUMENTS + 1):
            filename = f"stress_test_doc_{i:03d}.pdf"
            self.document_filenames.append(filename)
            
            logger.info(f"Generating document {i}/{self.config.NUM_DOCUMENTS}: {filename}")
            pdf_bytes = DocumentGenerator.create_pdf(i, filename)
            documents.append((i, filename, pdf_bytes))
        
        logger.info(f"✓ Generated {len(documents)} unique PDF documents")
        logger.info(f"Starting uploads with {self.config.CONCURRENT_UPLOADS} concurrent connections...")
        
        # Upload in batches
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(documents), self.config.CONCURRENT_UPLOADS):
                batch = documents[i:i + self.config.CONCURRENT_UPLOADS]
                batch_num = (i // self.config.CONCURRENT_UPLOADS) + 1
                total_batches = (len(documents) + self.config.CONCURRENT_UPLOADS - 1) // self.config.CONCURRENT_UPLOADS
                
                logger.info(f"\n--- Uploading Batch {batch_num}/{total_batches} ---")
                await self.upload_batch(session, batch)
                
                # Log batch summary
                summary = self.upload_stats.get_summary()
                logger.info(f"Progress: {summary['successful']}/{self.config.NUM_DOCUMENTS} successful, "
                          f"{summary['failed']} failed")
            
            self.upload_stats.end_time = time.time()
            
            # Trigger embedding pipeline if uploads were successful
            if self.upload_stats.successful_uploads > 0:
                logger.info("\n" + "-"*80)
                await self.trigger_embedding_pipeline(session)
    
    def print_final_report(self):
        """Print comprehensive test report"""
        logger.info("\n" + "="*80)
        logger.info("STRESS TEST FINAL REPORT")
        logger.info("="*80)
        
        # Upload Phase Summary
        upload_summary = self.upload_stats.get_summary()
        logger.info("\n>>> UPLOAD PHASE SUMMARY <<<")
        logger.info(f"Total upload attempts: {upload_summary['total_attempts']}")
        logger.info(f"Successful uploads: {upload_summary['successful']}")
        logger.info(f"Failed uploads: {upload_summary['failed']}")
        logger.info(f"Success rate: {upload_summary['success_rate']:.2f}%")
        logger.info(f"Average upload time: {upload_summary['avg_upload_time']:.2f}s")
        logger.info(f"Min upload time: {upload_summary['min_upload_time']:.2f}s")
        logger.info(f"Max upload time: {upload_summary['max_upload_time']:.2f}s")
        logger.info(f"Total upload duration: {upload_summary['total_duration']:.2f}s")
        
        if upload_summary['errors']:
            logger.info("\nUpload Errors:")
            for error, count in upload_summary['errors'].items():
                logger.info(f"  - {error}: {count} occurrences")
        
        # Embedding Phase Summary
        embedding_summary = self.embedding_stats.get_summary()
        logger.info("\n>>> EMBEDDING PHASE SUMMARY <<<")
        logger.info(f"Successful tasks: {embedding_summary['successful_tasks']}")
        logger.info(f"Failed tasks: {embedding_summary['failed_tasks']}")
        logger.info(f"Pending tasks: {embedding_summary['pending_tasks']}")
        logger.info(f"Average task duration: {embedding_summary['avg_task_duration']:.2f}s")
        logger.info(f"Total monitoring duration: {embedding_summary['total_monitoring_duration']:.2f}s")
        
        if embedding_summary['status_breakdown']:
            logger.info("\nTask Status Breakdown:")
            for status, count in embedding_summary['status_breakdown'].items():
                logger.info(f"  - {status}: {count} tasks")
        
        # Overall Assessment
        logger.info("\n>>> OVERALL ASSESSMENT <<<")
        upload_success = upload_summary['success_rate'] >= 95
        embedding_success = (
            embedding_summary['successful_tasks'] >= self.config.NUM_DOCUMENTS * 0.95
            and embedding_summary['failed_tasks'] == 0
        )
        
        if upload_success and embedding_success:
            logger.info("✓ STRESS TEST PASSED")
            logger.info("  System successfully handled 100 concurrent document uploads and embeddings")
        else:
            logger.warning("✗ STRESS TEST FAILED")
            if not upload_success:
                logger.warning(f"  Upload success rate too low: {upload_summary['success_rate']:.2f}%")
            if not embedding_success:
                logger.warning(f"  Embedding tasks incomplete or failed")
        
        logger.info("\n" + "="*80)
    
    async def run(self):
        """Run the complete stress test"""
        # Use UTC time for consistent comparison with Celery task timestamps
        test_start_time = datetime.now(timezone.utc)
        
        logger.info("\n" + "="*80)
        logger.info("DOCUMENT UPLOAD STRESS TEST")
        logger.info("="*80)
        logger.info(f"Test started at: {test_start_time.isoformat()}")
        logger.info(f"Configuration:")
        logger.info(f"  - Number of documents: {self.config.NUM_DOCUMENTS}")
        logger.info(f"  - Pages per document: {self.config.PAGES_PER_DOC}")
        logger.info(f"  - Concurrent uploads: {self.config.CONCURRENT_UPLOADS}")
        logger.info(f"  - API endpoint: {self.config.UPLOAD_ENDPOINT}")
        logger.info(f"  - MongoDB: {self.config.MONGODB_HOST}:{self.config.MONGODB_PORT}")
        logger.info("="*80)
        
        try:
            # Connect to MongoDB for monitoring
            logger.info("Connecting to MongoDB for task monitoring...")
            self.celery_monitor.connect()
            
            # Phase 1: Upload documents
            await self.run_upload_phase()
            
            # Phase 2: Monitor Celery tasks
            if self.upload_stats.successful_uploads > 0:
                # Wait a bit for tasks to be queued
                logger.info("\nWaiting 10 seconds for tasks to be queued...")
                await asyncio.sleep(10)
                
                self.monitor_celery_tasks(test_start_time)
            else:
                logger.error("No successful uploads - skipping Celery monitoring phase")
            
            # Print final report
            self.print_final_report()
            
        except Exception as e:
            logger.error(f"Stress test failed with error: {e}", exc_info=True)
        finally:
            # Cleanup
            self.celery_monitor.disconnect()
            
            test_end_time = datetime.now(timezone.utc)
            total_duration = (test_end_time - test_start_time).total_seconds()
            logger.info(f"\nTest ended at: {test_end_time.isoformat()}")
            logger.info(f"Total test duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes)")


async def main():
    """Main entry point"""
    config = StressTestConfig()
    runner = StressTestRunner(config)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())

