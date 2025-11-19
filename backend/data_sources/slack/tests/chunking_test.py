from data_sources.slack.slack_chunker_strategy import SlackChunkerStrategy

def slack_chunker():
    # Sample individual messages
    sample_messages = [
        {
            "time_stamp": "1609459200.000700",
            "user": "U012A3CDE",
            "text": "Has anyone looked at the latest revenue numbers?",
            "metadata": {
                "channel_name": "finance"
            }
        },
        {
            "time_stamp": "1609459230.000800",  # 30 seconds later
            "user": "U012A3CDF",
            "text": "Yes, they're looking good for Q3!",
            "metadata": {
                "channel_name": "finance"
            }
        },
        {
            "time_stamp": "1609459500.000900",  # 5 minutes later
            "user": "U012A3CDG",
            "text": "What's on the agenda for today's meeting?",
            "metadata": {
                "channel_name": "finance"
            }
        },
                {
            "time_stamp": "1609460500.000900",
            "user": "U028A3CDG",
            "text": "Hey, anyone is here? That's only a debug meesage, I expect it to be treated as single separated chunk",
            "metadata": {
                "channel_name": "finance"
            }
        }
    ]
    
    # Sample thread
    sample_thread = [
        [
            {
                "time_stamp": "1609460000.001000",
                "user": "U012A3CDE",
                "text": "Should we implement the new feature now or wait until next sprint?",
                "metadata": {
                    "channel_name": "engineering",
                    "thread_ts": "1609460000.001000"
                }
            },
            {
                "time_stamp": "1609460060.001100",
                "user": "U012A3CDF",
                "text": "I think we should wait, we have too many priorities this sprint already.",
                "metadata": {
                    "channel_name": "engineering",
                    "thread_ts": "1609460000.001000"
                }
            },
            {
                "time_stamp": "1609460120.001200",
                "user": "U012A3CDG",
                "text": "Agreed, let's put it in the backlog for next sprint planning.",
                "metadata": {
                    "channel_name": "engineering",
                    "thread_ts": "1609460000.001000"
                }
            }
        ]
    ]
    
    # Initialize chunker
    chunker = SlackChunkerStrategy(
        max_tokens_per_chunk=500,
        overlap_tokens=50,
        time_window_seconds=300
    )
    
    # Chunk individual messages
    message_chunks = chunker.chunk_content(sample_messages)
    print(f"Generated {len(message_chunks)} chunks from individual messages")
    
    # Reset and chunk threads
    chunker = SlackChunkerStrategy()
    thread_chunks = chunker.chunk_content(sample_thread)
    print(f"Generated {len(thread_chunks)} chunks from threads")