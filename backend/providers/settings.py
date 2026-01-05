from config.app_config import AppConfig
from shared.logger import logger
from functools import lru_cache
from utils.analytics.umami import UmamiAnalytics


app_config = AppConfig.get_instance()

@lru_cache(maxsize=1)
def get_umami_settings():
    """
    Get Umami analytics configuration including website ID.

    Returns:
        dict: Dictionary containing umami_url and website_id
        
    Raises:
        ValueError: If configuration is invalid or website not found
        Exception: For other API errors
    """
    try:        
        umami_url = app_config.get("umami_url", "")
        umami_website_name = app_config.get("umami_website_name", "unifai")
        umami_username = app_config.get("umami_username", "")
        umami_password = app_config.get("umami_password", "")        
        
        # Validate the website name if it is configured
        if not umami_website_name or umami_website_name == "dummy":
            raise ValueError("Website name is not configured")
        umami = UmamiAnalytics(umami_url, umami_username, umami_password)

        return umami.get_website_id(umami_website_name)
    except ValueError as e:
        # Configuration or website not found errors
        logger.error(f"Umami configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get Umami website ID: {e}")
        raise

