"""DataSource view definitions for controlling data retrieval depth."""
from enum import Enum


class DataSourceView(Enum):
    """Defines how much data to fetch for a DataSource.
    
    Used to control the amount of data returned from queries,
    allowing callers to request lightweight or full representations.
    
    Attributes:
        SUMMARY: Lightweight representation for list views - excludes heavy 
                 content fields like full_text for better performance
        FULL: Complete data including all content fields
    """
    SUMMARY = "summary"
    FULL = "full"
