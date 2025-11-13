"""
Tool for getting current date and time.
"""

from typing import Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from elements.tools.common.base_tool import BaseTool
from elements.nodes.common.agent.constants import ToolNames


class GetCurrentTimeArgs(BaseModel):
    """Arguments for getting current time."""
    timezone_name: str = Field(
        default="UTC",
        description="Timezone name (e.g., 'UTC', 'US/Eastern', 'Europe/London'). Defaults to UTC."
    )
    include_timestamp: bool = Field(
        default=True,
        description="Whether to include Unix timestamp in the response"
    )


class GetCurrentTimeTool(BaseTool):
    """Get current date and time information."""
    
    name = ToolNames.TIME_GET_CURRENT
    description = """Get the current date and time.
    
Essential for handling date/time-relative queries like "last week", "yesterday", "2 hours ago", "next month", or any task requiring current date/time context.

Returns current date, time, day of week, and timezone info."""
    
    args_schema = GetCurrentTimeArgs
    
    def __init__(self):
        """Initialize time tool (no dependencies needed)."""
        pass
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Get current time and date information."""
        
        args = GetCurrentTimeArgs(**kwargs)
        
        # Get current time in UTC
        now_utc = datetime.now(timezone.utc)
        
        # Try to convert to requested timezone
        try:
            if args.timezone_name != "UTC":
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(args.timezone_name)
                now_local = now_utc.astimezone(tz)
            else:
                now_local = now_utc
        except Exception:
            # Fallback to UTC if timezone is invalid
            now_local = now_utc
            args.timezone_name = "UTC"
        
        # Format the response
        result = {
            "datetime": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now_local.strftime("%Y-%m-%d"),
            "time": now_local.strftime("%H:%M:%S"),
            "day_of_week": now_local.strftime("%A"),
            "iso_format": now_local.isoformat(),
            "timezone": args.timezone_name,
            "human_readable": f"{now_local.strftime('%A, %B %d, %Y at %I:%M:%S %p')} {args.timezone_name}"
        }
        
        # Add timestamp if requested
        if args.include_timestamp:
            result["timestamp"] = int(now_local.timestamp())
        
        return result

