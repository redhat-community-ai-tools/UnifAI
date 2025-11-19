from typing import List, Tuple, Set
from pymongo import MongoClient
from pymongo.collection import Collection

class MongoConnection:
    """Manages MongoDB connection and collection indexing."""
    
    def __init__(self, mongo_uri: str):
        self.client = MongoClient(mongo_uri)
        self._indexed: Set[str] = set()

    def get_collection(self, db: str, col: str, indexes: List[Tuple[str, bool]] = None) -> Collection:
        """
        Get a collection and ensure it has the required indexes.
        
        Args:
            db: Database name
            col: Collection name  
            indexes: List of (field_name, unique) tuples for indexing
        
        Returns:
            MongoDB collection with indexes created
        """
        collection = self.client[db][col]
        key = f"{db}.{col}"

        if key not in self._indexed and indexes:
            for field, unique in indexes:
                collection.create_index([(field, 1)], unique=unique)
            self._indexed.add(key)

        return collection 