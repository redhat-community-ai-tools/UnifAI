from data_sources.slack.slack_config_manager import SlackConfigManager
from data_sources.slack.slack_connector import SlackConnector
from providers.data_sources import initialize_embedding_generator, initialize_vector_storage
from config.constants import SourceType
from config.app_config import AppConfig

def _get_configured_connector() -> SlackConnector:
    app_config = AppConfig.get_instance()
    config_manager = SlackConfigManager()
    config_manager.set_project_tokens(
        project_id="example-project",
        bot_token=app_config.default_slack_bot_token,
        user_token=app_config.default_slack_user_token
    )
    config_manager.set_default_project("example-project")
    return SlackConnector(config_manager)

def fetch_available_slack_channels():
    connector = _get_configured_connector()
    if connector.authenticate():
        return connector.fetch_available_slack_channels()
    else:
        raise RuntimeError("Slack authentication failed")

def get_available_slack_channels(channel_types: str, cursor: str = "", limit: int = 50, search_regex: str = None):
    connector = _get_configured_connector()
    if connector.authenticate():
        return connector.get_available_slack_channels_from_cache(types=channel_types, cursor=cursor, limit=limit, search_regex=search_regex)
    else:
        raise RuntimeError("Slack authentication failed")

def get_slack_user_info(user_id: str = None, include_locale: bool = False):
    """
    Get user information from Slack using the users.info API.
    
    Args:
        user_id: User ID to get info for. If None, gets info for the current authenticated user.
        include_locale: Whether to include locale information in the response.
        
    Returns:
        Dictionary containing user information from Slack API
        
    Raises:
        RuntimeError: If Slack authentication fails
        Exception: If the API request fails
    """
    connector = _get_configured_connector()
    if connector.authenticate():
        return connector.get_user_info(user_id=user_id, include_locale=include_locale)
    else:
        raise RuntimeError("Slack authentication failed")

def count_channel_chunks(channel_name: str) -> int:
    vector_storage = initialize_vector_storage(source_type=SourceType.SLACK.value)
    return vector_storage.count(filters={"metadata.channel_name": channel_name})

def get_best_match_results(query: str, top_k_results: int = 5, scope: str = "public", logged_in_user: str = "default"):
    embedding_generator = initialize_embedding_generator()
    vector_storage = initialize_vector_storage(embedding_generator.embedding_dim, SourceType.SLACK.value)
    
    query_embedding = embedding_generator.generate_query_embedding(query)
    
    search_results = vector_storage.search(
        query_embedding=query_embedding,
        top_k=top_k_results,
        filters={"upload_by": logged_in_user} if scope == "private" else {}
    )
    return search_results