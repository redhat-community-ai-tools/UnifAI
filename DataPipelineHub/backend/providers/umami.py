import requests
from config.app_config import AppConfig
from shared.logger import logger

def get_umami_api_url():
    """Return Umami API URL."""
    app_config = AppConfig.get_instance()
    umami_api_url = app_config.get("umami_api_url", "https://umami.example.com/api")
    return umami_api_url

def get_website_id():
    """Return website ID from Umami website."""
    try:
        umami_api_url = get_umami_api_url()
        response = requests.get(f"{umami_api_url}/websites")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get website ID: {e}")
        return None