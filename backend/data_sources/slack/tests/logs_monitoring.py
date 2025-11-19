

import pymongo
from data_sources.slack.slack_pipeline_scheduler import SlackDataPipeline
from utils.monitor.pipeline_monitor import PipelineMonitor
from utils.monitor.slack.slack_pipeline_monitor import SlackPipelineMonitor
    
def monitor_logs_demo():
    """
    Demonstrate log monitoring capabilities.
    
    This function shows how to use the log monitoring feature of the Pipeline Monitor
    to automatically track pipeline progress from log files.
    """
    # Initialize MongoDB client
    mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
    
    # Create pipeline monitor
    monitor = PipelineMonitor(mongo_client)
    
    # Process sample log lines
    sample_logs = [
        "2025-05-04 03:19:30,185 - data_pipeline - INFO - Making API request to Slack endpoint: auth.test",
        "2025-05-04 03:19:30,515 - data_pipeline - INFO - Slack API request to auth.test successful",
        "2025-05-04 03:19:30,515 - data_pipeline - INFO - Successfully authenticated with Slack as tag-user2",
        "2025-05-04 03:19:30,515 - data_pipeline - INFO - Making API request to Slack endpoint: conversations.list",
        "2025-05-04 03:19:32,020 - data_pipeline - INFO - Retrieved 1000 messages from channel C06987R1601",
        "2025-05-04 03:19:34,884 - data_pipeline - INFO - Chunking complete. Generated 686 chunks from Slack content",
        "2025-05-04 03:19:38,998 - data_pipeline - INFO - Stored 686 embeddings in 0.05 seconds"
    ]
    
    # Get stats for the auto-detected pipeline
    slack_monitor = SlackPipelineMonitor(monitor)

    slackDataPipeline = SlackDataPipeline(mongo_client, monitor, slack_monitor)
    slackDataPipeline.process_slack_channel("C06987R1601", "random")

    for log_line in sample_logs:
        monitor.process_log_line(log_line, "slack_C06987R1601")

    pipeline_stats = slack_monitor.get_channel_stats("C06987R1601")
    monitor.finish_log_monitoring()
    
    print("Auto-detected pipeline stats:")
    print(f"Pipeline ID: {pipeline_stats.get('pipeline_id', 'unknown')}")
    print(f"Status: {pipeline_stats.get('status', 'unknown')}")
    print(f"Stats: {pipeline_stats.get('stats', {})}")