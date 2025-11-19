from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from .slack_thread_retriever import SlackThreadRetriever
from shared.logger import logger

class ThreadRetrieverWorker:
    def __init__(
        self,
        retriever: SlackThreadRetriever,
        max_workers: int = 10,
        thread_number: int = 1,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ):
        self.retriever = retriever
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []
        self.thread_number = thread_number
        self.oldest = oldest
        self.latest = latest

    def submit(self, channel_id: str, thread_ts: str):
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