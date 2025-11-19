from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

import tiktoken # used for accurate token counting (OpenAI's tokenizer)
from langchain.text_splitter import RecursiveCharacterTextSplitter # used for intelligent chunking at natural text boundaries

from shared.logger import logger
from utils.content_chunker import ContentChunker

class SlackChunkerStrategy(ContentChunker):
    """
    Chunking strategy specifically designed for Slack conversations.
    
    Implements a hybrid chunking approach that:
    1. Preserves threads as intact chunks when possible
    2. Groups non-threaded messages by time proximity (conversation bursts)
    3. Enforces token limits for all chunks
    4. Maintains source traceability and metadata
    """
    
    def __init__(
        self, 
        max_tokens_per_chunk: int = 500, 
        overlap_tokens: int = 50,
        time_window_seconds: int = 300  # 5 minutes in seconds
    ):
        """
        Initialize the Slack chunker with configuration parameters.
        
        Args:
            max_tokens_per_chunk: Maximum number of tokens allowed in a single chunk
            overlap_tokens: Number of tokens to overlap between adjacent chunks
            time_window_seconds: Maximum time difference between messages to consider them part of the same conversation
        """
        super().__init__(max_tokens_per_chunk, overlap_tokens)
        self.time_window_seconds = time_window_seconds
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # OpenAI's tokenizer, compatible with many embedding models
    
    def chunk_content(self, content: Union[List[Dict[str, Any]], List[List[Dict[str, Any]]]], upload_by: str = "default") -> List[Dict[str, Any]]:
        """
        Split Slack content into logical chunks using a hybrid strategy.
        
        This method handles both individual messages and thread messages,
        applying appropriate chunking strategies for each.
        
        Args:
            content: Either a list of processed messages or a list of thread message lists
            
        Returns:
            List of chunks with content and metadata
        """
        self._chunks = []
        
        # Determine if we're dealing with threads or individual messages
        if content and isinstance(content[0], list):
            logger.info(f"Processing {len(content)} Slack threads for chunking")
            self._chunk_threads(content, upload_by)
        else:
            logger.info(f"Processing {len(content)} individual Slack messages for chunking")
            self._chunk_individual_messages(content, upload_by)
        
        logger.info(f"Chunking complete. Generated {len(self._chunks)} chunks from Slack content")
        return self._chunks
    
    def _chunk_threads(self, threads: List[List[Dict[str, Any]]], upload_by) -> None:
        """
        Process thread messages, treating each thread as a potential chunk.
        
        Args:
            threads: List of threads, where each thread is a list of messages
        """
        for thread_index, thread in enumerate(threads):
            if not thread:
                continue
                
            # Sort messages by timestamp to ensure proper ordering
            thread = sorted(thread, key=lambda msg: float(msg["time_stamp"]))
            
            # Check if the entire thread can fit in a single chunk
            thread_text = self._format_thread_as_text(thread)
            token_count = self.estimate_token_count(thread_text)
            
            # Get common metadata from the thread
            channel_name = thread[0]["metadata"]["channel_name"]
            first_timestamp = thread[0]["time_stamp"]
            last_timestamp = thread[-1]["time_stamp"]
            
            if token_count <= self.max_tokens_per_chunk:
                # The entire thread fits within token limits
                self._chunks.append({
                    "text": thread_text,
                    "metadata": {
                        "source_type": "slack_thread",
                        "channel_name": channel_name,
                        "upload_by": upload_by,
                        "thread_id": thread[0].get("metadata", {}).get("thread_ts", first_timestamp),
                        "time_range": f"{first_timestamp}-{last_timestamp}",
                        "message_count": len(thread),
                        "token_count": token_count
                    }
                })
            else:
                # Thread exceeds token limits, split it using LangChain's text splitter
                logger.debug(f"Thread {thread_index} exceeds token limit. Splitting into smaller chunks.")
                self._split_large_content(thread_text, {
                    "source_type": "slack_thread",
                    "channel_name": channel_name,
                    "upload_by": upload_by,
                    "thread_id": thread[0].get("metadata", {}).get("thread_ts", first_timestamp),
                    "time_range": f"{first_timestamp}-{last_timestamp}",
                    "message_count": len(thread),
                    "is_split": True
                })
    
    def _chunk_individual_messages(self, messages: List[Dict[str, Any]], upload_by) -> None:
        """
        Process individual messages by grouping them into time-based conversation bursts.
        
        Args:
            messages: List of individual messages (not part of threads)
        """
        if not messages:
            return
            
        # Sort messages by timestamp
        messages = sorted(messages, key=lambda msg: float(msg["time_stamp"]))
        
        # Group messages by time proximity (conversation bursts)
        conversation_groups = []
        current_group = [messages[0]]
        
        for i in range(1, len(messages)):
            current_msg = messages[i]
            prev_msg = messages[i-1]
            
            time_diff = float(current_msg["time_stamp"]) - float(prev_msg["time_stamp"])
            
            if time_diff <= self.time_window_seconds:
                # Messages are close enough in time, add to current group
                current_group.append(current_msg)
            else:
                # Time gap exceeds window, start a new conversation group
                conversation_groups.append(current_group)
                current_group = [current_msg]
        
        # Add the last group if it exists
        if current_group:
            conversation_groups.append(current_group)
        
        logger.info(f"Grouped {len(messages)} messages into {len(conversation_groups)} conversation bursts")
        
        # Process each conversation group
        for group_index, group in enumerate(conversation_groups):
            channel_name = group[0]["metadata"]["channel_name"]
            first_timestamp = group[0]["time_stamp"]
            last_timestamp = group[-1]["time_stamp"]
            
            # Format the conversation as text
            conversation_text = self._format_messages_as_text(group)
            token_count = self.estimate_token_count(conversation_text)
            
            if token_count <= self.max_tokens_per_chunk:
                # Conversation fits within token limits
                self._chunks.append({
                    "text": conversation_text,
                    "metadata": {
                        "source_type": "slack_conversation",
                        "channel_name": channel_name,
                        "upload_by": upload_by,
                        "time_range": f"{first_timestamp}-{last_timestamp}",
                        "message_count": len(group),
                        "token_count": token_count
                    }
                })
            else:
                # Conversation exceeds token limits, split it
                logger.debug(f"Conversation group {group_index} exceeds token limit. Splitting into smaller chunks.")
                self._split_large_content(conversation_text, {
                    "source_type": "slack_conversation",
                    "channel_name": channel_name,
                    "upload_by": upload_by,
                    "time_range": f"{first_timestamp}-{last_timestamp}",
                    "message_count": len(group),
                    "is_split": True
                })
    
    def _split_large_content(self, text: str, metadata: Dict[str, Any]) -> None:
        """
        Split large content that exceeds token limits into smaller chunks.
        
        Uses LangChain's RecursiveCharacterTextSplitter for intelligent splitting
        at natural text boundaries like paragraph breaks, sentences, etc.
        
        Args:
            text: Text content to split
            metadata: Metadata to associate with the resulting chunks
        """
        # Calculate approximately how many characters per token for this content
        chars_per_token = len(text) / max(1, self.estimate_token_count(text))
        
        # Convert token limits to character estimates for the text splitter
        max_chunk_size = int(self.max_tokens_per_chunk * chars_per_token)
        chunk_overlap = int(self.overlap_tokens * chars_per_token)
        
        # Create a recursive text splitter that tries to break at natural boundaries
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=lambda text: self.estimate_token_count(text),
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Split the text
        chunk_texts = text_splitter.split_text(text)
        
        # Create chunks with metadata
        for i, chunk_text in enumerate(chunk_texts):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["chunk_count"] = len(chunk_texts)
            chunk_metadata["token_count"] = self.estimate_token_count(chunk_text)
            
            self._chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })
    
    def _format_thread_as_text(self, thread_messages: List[Dict[str, Any]]) -> str:
        """
        Format thread messages into a human-readable text representation.
        
        Args:
            thread_messages: List of messages in a thread
            
        Returns:
            Formatted text representation of the thread
        """
        lines = []
        
        # Add thread header
        channel = thread_messages[0]["metadata"]["channel_name"]
        thread_ts = thread_messages[0].get("metadata", {}).get("thread_ts", thread_messages[0]["time_stamp"])
        lines.append(f"Slack Thread in #{channel} - Thread ID: {thread_ts}")
        lines.append("=" * 50)
        
        # Format each message in the thread
        for msg in thread_messages:
            timestamp = float(msg["time_stamp"])
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            user = msg["user"]
            text = msg["text"]
            
            lines.append(f"[{time_str}] {user}: {text}")
        
        return "\n".join(lines)
    
    def _format_messages_as_text(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format individual messages into a human-readable conversation.
        
        Args:
            messages: List of messages to format
            
        Returns:
            Formatted text representation of the conversation
        """
        lines = []
        
        # Add conversation header
        channel = messages[0]["metadata"]["channel_name"]
        start_time = datetime.fromtimestamp(float(messages[0]["time_stamp"])).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.fromtimestamp(float(messages[-1]["time_stamp"])).strftime('%Y-%m-%d %H:%M:%S')
        
        lines.append(f"Slack Conversation in #{channel} - {start_time} to {end_time}")
        lines.append("=" * 50)
        
        # Format each message
        for msg in messages:
            timestamp = float(msg["time_stamp"])
            time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
            user = msg["user"]
            text = msg["text"]
            
            lines.append(f"[{time_str}] {user}: {text}")
        
        return "\n".join(lines)
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string using tiktoken.
        
        Args:
            text: Text to tokenize
            
        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0
            
        tokens = self.tokenizer.encode(text)
        return len(tokens)