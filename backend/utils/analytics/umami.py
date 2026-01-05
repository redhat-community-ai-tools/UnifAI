from shared.logger import logger
import umami

class UmamiAnalytics():
    """
    Umami Analytics client wrapper.
    Handles authentication and website information retrieval.
    """
    
    def __init__(self, url: str, username: str, password: str):
        """
        Initialize Umami Analytics client.
        
        Args:
            url: Umami service URL
            username: Umami login username
            password: Umami login password
        """
        self.url = url
        self.username = username
        self.password = password
        self.umami = umami
        self.logger = logger
        self._website_cache = {}
        self.validate_umami_params(url, username, password)
        self.login()

    def login(self):
        """Authenticate with Umami service."""
        self.umami.set_url_base(self.url)
        self.umami.login(self.username, self.password)

    def validate_umami_params(self, url: str, username: str, password: str) -> None:
        """
        Validate Umami configuration parameters.
        
        Args:
            url: Umami service URL
            username: Umami login username
            password: Umami login password
            
        Raises:
            ValueError: If any parameter is invalid or missing
        """
        if not url or url == "0.0.0.0":
            raise ValueError("Umami URL is not configured")
        if not username or username == "dummy":
            raise ValueError("Umami username is not configured")
        if not password or password == "dummy":
            raise ValueError("Umami password is not configured")

    def get_website_id(self, website_name: str) -> dict:
        """
        Get website ID from Umami by website name.
        Caches results to avoid repeated API calls.
        
        Args:
            website_name: Name of the website in Umami
            
        Returns:
            dict: Dictionary containing umami_url and website_id
            
        Raises:
            ValueError: If website not found
            Exception: For other API errors
        """        
        # Check cache first
        if website_name in self._website_cache:
            return self._website_cache[website_name]

        try:
            websites = self.umami.websites()
            website_info = next(w for w in websites if w.name == website_name)
            website_id = website_info.id
            result = {"umami_url": self.url, "website_id": website_id}

            # Cache the result to prevent repeated API calls
            self._website_cache[website_name] = result

            return result
        except StopIteration:
            self.logger.error(f"Umami website not found: {website_name}")
            raise ValueError(f"Website '{website_name}' not found in Umami")
        except Exception as e:
            self.logger.error(f"Failed to get Umami website ID: {website_name}: {e}")
            raise
