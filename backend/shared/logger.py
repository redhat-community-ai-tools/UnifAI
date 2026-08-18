import logging
import warnings
warnings.warn("shared.logger is deprecated; use logging.getLogger(__name__)", DeprecationWarning, stacklevel=2)
logger = logging.getLogger("platform-backend")
