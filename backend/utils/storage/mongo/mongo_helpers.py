"""
MongoDB Storage Helper Functions

Uses @lru_cache for simple singleton behavior that works in any context.
"""

from functools import lru_cache
from utils.storage.mongo.mongo_storage import MongoStorage
from global_utils.utils.util import get_mongo_url

@lru_cache(maxsize=1)
def get_mongo_storage() -> MongoStorage:
    """Get cached MongoDB storage - works in any context"""
    return MongoStorage(get_mongo_url())
