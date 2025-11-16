from __future__ import annotations
import re
from datetime import datetime, timedelta

def parse_date_range_to_days(date_range: str) -> int:
    """
    Parse date range string into number of days.
    Supports formats like: "7d", "30d", "1m", "1y"
    
    Args:
        date_range: String like "7d", "30d", etc.
        
    Returns:
        Number of days to go back
    """
    if not date_range:
        return 30 
       
    date_range = date_range.lower().strip()
    # Special case: UI sends "all" for all-time selection
    if date_range in {"all", "all_time", "alltime"}:
        return 36500  # ~100 years
    
    compact_match = re.search(r'(\d+)([dmyh])', date_range)
    if compact_match:
        number = int(compact_match.group(1))
        unit = compact_match.group(2)
        
        if unit == 'd':
            return number
        elif unit == 'm':
            return number * 30
        elif unit == 'y':
            return number * 365
        elif unit == 'h':
            return max(1, number // 24)
    
    return 30

def calculate_date_range(date_range: str) -> tuple[datetime, datetime]:
    """
    Calculate start and end datetime objects based on date range.
    
    Args:
        date_range: String like "7d", "30d", etc.
        
    Returns:
        Tuple of (start_datetime, end_datetime)
        
    Example:
        If today is 2025-01-05 and date_range is "7d":
        - start_datetime: 2024-12-29 00:00:00 (7 days ago at midnight)
        - end_datetime: 2025-01-05 14:30:15 (current datetime)
    """
    end_datetime = datetime.now()
    
    if not date_range:
        days_back = 30
    else:
        days_back = parse_date_range_to_days(date_range)
    
    start_date = (end_datetime - timedelta(days=days_back)).date()
    start_datetime = datetime.combine(start_date, datetime.min.time())
    
    return start_datetime, end_datetime


def get_time_range_bounds_from_type_data(
    type_data: dict | None,
    *,
    start_key: str = "start_timestamp",
    end_key: str = "end_timestamp",
    output: str = "iso",
) -> tuple[object | None, object | None]:
    """
    Generic converter to extract start/end from a mapping and format them.

    - Accepts ISO strings (with optional trailing 'Z') or datetime objects
    - Returns (start, end) formatted per `output`:
        - "datetime": datetime objects
        - "iso": ISO 8601 strings
        - "unix_seconds": float seconds since epoch
        - "unix_millis": int milliseconds since epoch
        - "slack_ts": string representation of unix seconds (for Slack APIs)
    - Missing or invalid values return None
    - Keys are configurable via start_key/end_key
    """
    if not type_data:
        return None, None

    def _to_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        try:
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            if isinstance(value, datetime):
                return value
        except Exception:
            return None
        return None

    start_dt = _to_datetime(type_data.get(start_key))
    end_dt = _to_datetime(type_data.get(end_key))

    def _format(dt: datetime | None) -> object | None:
        if dt is None:
            return None
        if output == "datetime":
            return dt
        if output == "iso":
            return dt.isoformat()
        if output == "unix_seconds":
            return dt.timestamp()
        if output == "unix_millis":
            return int(dt.timestamp() * 1000)
        if output == "slack_ts":
            return str(dt.timestamp())
        # Fallback to iso if unknown format
        return dt.isoformat()

    return _format(start_dt), _format(end_dt)
