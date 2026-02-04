"""Slack thread retriever worker - concurrent thread fetching for SlackConnector."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from infrastructure.sources.slack.thread_retriever import SlackThreadRetriever
from shared.logger import logger


class ThreadRetrieverWorker:
    """
    Worker class for concurrent retrieval of Slack thread replies.
    
    Uses a thread pool to fetch multiple threads in parallel,
    improving performance when processing channels with many threads.
    """
    
    def __init__(
        self,
        retriever: SlackThreadRetriever,
        max_workers: int = 10,
        thread_number: int = 1,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ):
        """
        Initialize the thread retriever worker.
        
        Args:
            retriever: SlackThreadRetriever instance for making API calls
            max_workers: Maximum number of concurrent threads (default: 10)
            thread_number: Starting thread number for logging (default: 1)
            oldest: Optional oldest timestamp filter
            latest: Optional latest timestamp filter
        """
        self.retriever = retriever
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []
        self.thread_number = thread_number
        self.oldest = oldest
        self.latest = latest

    def submit(self, channel_id: str, thread_ts: str):
        """
        Submit a thread for retrieval.
        
        Args:
            channel_id: The channel ID where the thread is located
            thread_ts: The timestamp of the parent message
        """
        future = self.executor.submit(
            self.retriever.get_thread_replies,
            channel_id,
            thread_ts,
            self.thread_number,
            self.oldest,
            self.latest,
        )
        self.thread_number = self.thread_number + 1
        self.futures.append(future)

    def gather_results(self) -> List[List[Dict[str, Any]]]:
        """
        Wait for all submitted threads to complete and gather results.
        
        Returns:
            List of thread message lists (each inner list contains messages from one thread)
        """
        results = []
        for future in as_completed(self.futures):
            try:
                replies = future.result()
                if replies:
                    results.append(replies)
            except Exception as e:
                logger.exception(f"Exception while retrieving thread replies: {e}")
        self.executor.shutdown(wait=True)
        return results
