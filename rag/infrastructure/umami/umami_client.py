"""Umami Analytics client - external API adapter."""
from typing import Dict, Any

import umami

from shared.logger import logger


class UmamiClient:
    """
    Infrastructure adapter for Umami Analytics API.
    
    Handles authentication and website information retrieval
    from the Umami analytics service.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
    ):
        """
        Initialize Umami client.
        
        Args:
            url: Umami service URL
            username: Umami login username
            password: Umami login password
            
        Raises:
            ValueError: If configuration is invalid
        """
        self._url = url
        self._username = username
        self._password = password
        self._website_cache: Dict[str, Dict[str, Any]] = {}
        
        self._validate_config()
        self._login()

    def _validate_config(self) -> None:
        """Validate Umami configuration parameters."""
        if not self._url or self._url == "0.0.0.0":
            raise ValueError("Umami URL is not configured")
        if not self._username or self._username == "dummy":
            raise ValueError("Umami username is not configured")
        if not self._password or self._password == "dummy":
            raise ValueError("Umami password is not configured")

    def _login(self) -> None:
        """Authenticate with Umami service."""
        umami.set_url_base(self._url)
        umami.login(self._username, self._password)
        logger.info("Umami client authenticated successfully")

    def get_website_id(self, website_name: str) -> Dict[str, Any]:
        """
        Get website ID from Umami by website name.
        
        Results are cached to avoid repeated API calls.
        
        Args:
            website_name: Name of the website in Umami
            
        Returns:
            Dict with umami_url and website_id
            
        Raises:
            ValueError: If website not found
        """
        # Check cache first
        if website_name in self._website_cache:
            return self._website_cache[website_name]

        try:
            websites = umami.websites()
            website_info = next(w for w in websites if w.name == website_name)
            
            result = {
                "umami_url": self._url,
                "website_id": website_info.id,
            }
            
            # Cache the result
            self._website_cache[website_name] = result
            logger.info(f"Retrieved Umami website ID for: {website_name}")
            
            return result
            
        except StopIteration:
            logger.error(f"Umami website not found: {website_name}")
            raise ValueError(f"Website '{website_name}' not found in Umami")
        except Exception as e:
            logger.error(f"Failed to get Umami website ID for {website_name}: {e}")
            raise

