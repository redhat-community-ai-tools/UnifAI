
import sys
import pymongo
from shared.logger import logger
from data_sources.slack.slack_config_manager import SlackConfigManager
from data_sources.slack.slack_connector import SlackConnector

from data_sources.slack.slack_data_processor import SlackProcessor
from data_sources.slack.slack_chunker_strategy import SlackChunkerStrategy
from data_sources.slack.slack_pipeline_scheduler import SlackDataPipeline
from utils.embedding.embedding_generator_factory import EmbeddingGeneratorFactory
from utils.storage.vector_storage_factory import VectorStorageFactory

from .logs_monitoring import monitor_logs_demo
from .chunking_test import slack_chunker
from .embedding_test import embedding_flow
from .retrieval_test import rag_flow

def slack_flow():
    """Example usage of the Slack pipeline components."""
    # Create MongoDB client
    mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
    
    # Create data pipeline with existing logger
    slack_pipeline = SlackDataPipeline(mongo_client, logger=logger)

    # Create configuration manager
    config_manager = SlackConfigManager()
    
    # Set up a project with tokens (in real usage, load from environment or secure storage)
    config_manager.set_project_tokens(
        project_id="example-project",
        bot_token="xoxb-2253118358-8783454711008-dwnxf7cPBpeVLlLw8KMurohb",
        user_token="xoxb-2253118358-8783454711008-dwnxf7cPBpeVLlLw8KMurohb"
    )
    
    config_manager.set_default_project("example-project")
    
    # Create a connector
    try:
        connector = SlackConnector(config_manager)
        
        # Test authentication
        if connector.authenticate():
            # Get available channels
            channels = connector.get_available_slack_channels_from_cache(types="private_channel")
            print(f"Found {len(channels)} channels")
            
            # Get history for the first channel if available
            if channels:
                first_channel = channels[0]
               # Process the slack channel using our pipeline
                slack_pipeline.process_slack_channel(first_channel['channel_id'], first_channel['channel_name'])

                # Start log monitoring - this will uses the event-driven handler system
                slack_pipeline.monitor.start_log_monitoring(target_logger=logger, pipeline_id=f"slack_{first_channel['channel_id']}")

                print(f"Getting messages for channel: {first_channel['channel_name']}")
                messages, thread_messages = connector.get_conversations_history(first_channel['channel_id'])
                print(f"Retrieved {len(messages)} messages")
                print(f"Retrieved {len(thread_messages)} thread_messages")
            
                # Initialize and use processor
                processor = SlackProcessor()
                processed_data = processor.process(messages, channel_name=first_channel['channel_name'])

                # Reset and chunk threads
                chunker = SlackChunkerStrategy()
                messages_chunks = chunker.chunk_content(processed_data)
                print(f"Generated {len(messages_chunks)} chunks from messages")

                # Display results
                # for msg in processed_data:
                #     print(f"User: {msg['user']}, Message: {msg['text']}")

                processed_thread_data = []
                for msg in thread_messages:
                    processed_single_thread_data = processor.process(msg, channel_name="random")
                    processed_thread_data.append(processed_single_thread_data)

                # # Initialize chunker
                chunker = SlackChunkerStrategy(
                    max_tokens_per_chunk=500,
                    overlap_tokens=50,
                    time_window_seconds=300
                )
                
                # Reset and chunk threads
                chunker = SlackChunkerStrategy()
                thread_chunks = chunker.chunk_content(processed_thread_data)
                # print(f"Generated {len(thread_chunks)} chunks from threads")

                # # Display results
                # # for sample_thread in thread_chunks:
                # #     print(sample_thread)

                # Create embedding generator
                embedding_config = {
                    "type": "sentence_transformer",
                    "model_name": "all-MiniLM-L6-v2",
                    "batch_size": 32
                }
                
                embedding_generator = EmbeddingGeneratorFactory.create(embedding_config)
                
                # Generate embeddings
                enriched_chunks = embedding_generator.generate_embeddings(thread_chunks)
                
                # Create vector storage
                storage_config = {
                    "type": "qdrant",
                    "collection_name": "slack_data",
                    "embedding_dim": embedding_generator.embedding_dim,
                    "url": "http://localhost",
                    "port": 6333
                }
                
                vector_storage = VectorStorageFactory.create(storage_config)
                
                # Initialize storage
                vector_storage.initialize()
                
                # Store embeddings
                vector_storage.store_embeddings(enriched_chunks)
                slack_pipeline.monitor.finish_log_monitoring()
                
    except Exception as e:
        logger.error(f"Error in slack_flow: {str(e)}")

if __name__ == "__main__":
    functions = {
        "slack_flow": slack_flow,
        "slack_chunker": slack_chunker,
        "embedding_flow": embedding_flow,
        "rag_flow": rag_flow,
        "monitor_logs_demo": monitor_logs_demo,
    }

    if len(sys.argv) < 2:
        print("Usage: python script.py <function_name>")
        print(f"Available functions: {', '.join(functions.keys())}")
        sys.exit(1)

    func_name = sys.argv[1]
    if func_name in functions:
        functions[func_name]()
    else:
        print(f"Unknown function '{func_name}'. Available options are: {', '.join(functions.keys())}")
        sys.exit(1)