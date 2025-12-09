"""
Analytics API endpoints for workflow session statistics.

Provides real-time analytics data fetched directly from MongoDB.
"""

from flask import Blueprint, jsonify, session, request
from global_utils.helpers.apiargs import from_query
from webargs import fields
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Any, Optional
import pymongo
from global_utils.utils.util import get_mongo_url
from global_utils.config import SharedConfig
from functools import wraps
import time

analytics_bp = Blueprint("analytics", __name__)

# Get MongoDB configuration
config = SharedConfig.get_instance()
MONGO_URI = get_mongo_url()
MONGO_DB = getattr(config, 'mongo_db', 'UnifAI')

# Simple in-memory cache with expiration
_analytics_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 60,  # Cache for 60 seconds
    'cache_key': None
}


def require_analytics_access(f):
    """Decorator to check if user has analytics access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Optional: Add analytics access check here if needed
        # For now, we rely on frontend access control
        return f(*args, **kwargs)
    return decorated_function


class WorkflowAnalytics:
    """Analyzes workflow sessions from MongoDB."""
    
    def __init__(self, mongo_uri: str, db_name: str):
        """Initialize with MongoDB connection."""
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db["workflow_sessions"]
        self.blueprints_collection = self.db["blueprints"]
        
        # Ensure indexes exist for better performance
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes on commonly queried fields to improve performance."""
        try:
            # Index on user_id for user-based queries
            self.collection.create_index([("user_id", pymongo.ASCENDING)])
            
            # Index on status for status breakdown queries
            self.collection.create_index([("status", pymongo.ASCENDING)])
            
            # Index on blueprint_id for blueprint usage queries
            self.collection.create_index([("blueprint_id", pymongo.ASCENDING)])
            
            # Index on started_at for time-based queries
            self.collection.create_index([("run_context.started_at", pymongo.DESCENDING)])
            
            # Compound index for user + time queries (active users)
            self.collection.create_index([
                ("user_id", pymongo.ASCENDING),
                ("run_context.started_at", pymongo.DESCENDING)
            ])
            
            # Index for blueprints collection
            self.blueprints_collection.create_index([("blueprint_id", pymongo.ASCENDING)])
            
        except Exception as e:
            print(f"Warning: Could not create indexes: {e}")
    
    def get_total_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        total_runs = self.collection.count_documents({})
        unique_users = len(self.collection.distinct("user_id"))
        
        return {
            "total_runs": total_runs,
            "unique_users": unique_users,
            "avg_runs_per_user": round(total_runs / unique_users, 2) if unique_users > 0 else 0
        }
    
    def get_status_breakdown(self) -> Dict[str, int]:
        """Get breakdown of runs by status."""
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        results = self.collection.aggregate(pipeline)
        return {doc["_id"]: doc["count"] for doc in results}
    
    def get_user_activity(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get activity breakdown by user."""
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "total_runs": {"$sum": 1},
                "statuses": {"$push": "$status"},
                "blueprints": {"$addToSet": "$blueprint_id"}
            }},
            {"$sort": {"total_runs": -1}},
            {"$limit": limit}
        ]
        
        results = []
        for doc in self.collection.aggregate(pipeline):
            # Count statuses
            status_counts = defaultdict(int)
            for status in doc["statuses"]:
                status_counts[status] += 1
            
            results.append({
                "user_id": doc["_id"],
                "total_runs": doc["total_runs"],
                "unique_blueprints": len(doc["blueprints"]),
                "status_breakdown": dict(status_counts)
            })
        
        return results
    
    def get_active_users(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get users active within the last N days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat().replace('+00:00', 'Z')
        
        pipeline = [
            {"$match": {
                "run_context.started_at": {"$gte": cutoff_iso}
            }},
            {"$group": {
                "_id": "$user_id",
                "recent_runs": {"$sum": 1},
                "last_run_id": {"$last": "$run_id"},
                "statuses": {"$push": "$status"}
            }},
            {"$sort": {"recent_runs": -1}}
        ]
        
        results = []
        for doc in self.collection.aggregate(pipeline):
            status_counts = defaultdict(int)
            for status in doc["statuses"]:
                status_counts[status] += 1
                
            results.append({
                "user_id": doc["_id"],
                "recent_runs": doc["recent_runs"],
                "last_run_id": doc["last_run_id"],
                "status_breakdown": dict(status_counts)
            })
        
        return results
    
    def get_active_users_today(self) -> List[Dict[str, Any]]:
        """Get users active today."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_iso = today_start.isoformat().replace('+00:00', 'Z')
        
        pipeline = [
            {"$match": {
                "run_context.started_at": {"$gte": today_start_iso}
            }},
            {"$group": {
                "_id": "$user_id",
                "runs_today": {"$sum": 1},
                "statuses": {"$push": "$status"},
                "last_run_id": {"$last": "$run_id"}
            }},
            {"$sort": {"runs_today": -1}}
        ]
        
        results = []
        for doc in self.collection.aggregate(pipeline):
            status_counts = defaultdict(int)
            for status in doc["statuses"]:
                status_counts[status] += 1
            
            results.append({
                "user_id": doc["_id"],
                "runs_today": doc["runs_today"],
                "status_breakdown": dict(status_counts),
                "last_run_id": doc["last_run_id"]
            })
        
        return results
    
    def get_time_based_stats(self) -> Dict[str, Any]:
        """Get time-based statistics."""
        earliest = self.collection.find_one(sort=[("run_context.start_timestamp", pymongo.ASCENDING)])
        latest = self.collection.find_one(sort=[("run_context.start_timestamp", pymongo.DESCENDING)])
        
        stats = {
            "earliest_run": None,
            "latest_run": None,
            "time_span_days": None
        }
        
        if earliest and latest:
            try:
                earliest_time = earliest.get("run_context", {}).get("start_timestamp")
                latest_time = latest.get("run_context", {}).get("start_timestamp")
                
                # Validate and convert timestamps
                def validate_timestamp(ts):
                    """Validate timestamp and return ISO format string or None."""
                    if ts is None:
                        return None
                    try:
                        if isinstance(ts, str):
                            # Validate ISO format string
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            return ts if 'Z' in ts else dt.isoformat() + 'Z'
                        elif isinstance(ts, (int, float)):
                            # Validate numeric timestamp (must be > 0 and reasonable)
                            if ts <= 0 or ts > 2147483647:  # Reject 0, negative, or unreasonably large
                                return None
                            dt = datetime.fromtimestamp(ts)
                            return dt.isoformat() + 'Z'
                        else:
                            return None
                    except (ValueError, TypeError, OSError):
                        return None
                
                earliest_valid = validate_timestamp(earliest_time)
                latest_valid = validate_timestamp(latest_time)
                
                # Only set earliest_run if timestamp is valid
                if earliest_valid:
                    stats["earliest_run"] = {
                        "run_id": earliest.get("run_id"),
                        "user_id": earliest.get("user_id"),
                        "timestamp": earliest_valid
                    }
                
                # Only set latest_run if timestamp is valid
                if latest_valid:
                    stats["latest_run"] = {
                        "run_id": latest.get("run_id"),
                        "user_id": latest.get("user_id"),
                        "timestamp": latest_valid
                    }
                
                # Calculate time span only if both timestamps are valid
                if earliest_valid and latest_valid:
                    try:
                        earliest_dt = datetime.fromisoformat(earliest_valid.replace('Z', '+00:00'))
                        latest_dt = datetime.fromisoformat(latest_valid.replace('Z', '+00:00'))
                        time_span = latest_dt - earliest_dt
                        stats["time_span_days"] = time_span.days
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass
        
        return stats
    
    def get_blueprint_usage(self, limit: int = 10, time_range: str = "all") -> List[Dict[str, Any]]:
        """Get most used blueprints, optionally filtered by time range."""
        now = datetime.now(timezone.utc)
        
        # Build match stage based on time range
        match_stage = {}
        if time_range != "all":
            if time_range == "today":
                cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == "7days":
                cutoff_date = now - timedelta(days=7)
            elif time_range == "30days":
                cutoff_date = now - timedelta(days=30)
            else:
                cutoff_date = None
            
            if cutoff_date:
                cutoff_iso = cutoff_date.isoformat().replace('+00:00', 'Z')
                match_stage["run_context.started_at"] = {"$gte": cutoff_iso}
        
        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        
        pipeline.extend([
            {"$group": {
                "_id": "$blueprint_id",
                "run_count": {"$sum": 1},
                "unique_users": {"$addToSet": "$user_id"}
            }},
            {"$sort": {"run_count": -1}},
            {"$limit": limit}
        ])
        
        results = []
        for doc in self.collection.aggregate(pipeline):
            blueprint_id = doc["_id"]
            
            # Try to fetch blueprint name
            blueprint_name = blueprint_id
            try:
                blueprint_doc = self.blueprints_collection.find_one({"blueprint_id": blueprint_id})
                if blueprint_doc:
                    spec_dict = blueprint_doc.get("spec_dict", {})
                    if isinstance(spec_dict, dict):
                        blueprint_name = spec_dict.get("name", blueprint_id)
            except Exception:
                pass
            
            results.append({
                "blueprint_id": blueprint_id,
                "blueprint_name": blueprint_name,
                "run_count": doc["run_count"],
                "unique_users": len(doc["unique_users"])
            })
        
        return results
    
    def get_hourly_activity(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get hourly activity distribution for the last N days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat().replace('+00:00', 'Z')
        
        pipeline = [
            {"$match": {
                "run_context.started_at": {"$gte": cutoff_iso}
            }},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d %H:00",
                        "date": {"$dateFromString": {"dateString": "$run_context.started_at"}}
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        try:
            results = list(self.collection.aggregate(pipeline))
            return [{"hour": doc["_id"], "count": doc["count"]} for doc in results]
        except Exception:
            return []
    
    def get_time_series_activity(self, time_range: str = "all") -> List[Dict[str, Any]]:
        """
        Get time series activity data grouped by appropriate time intervals.
        
        Args:
            time_range: 'today', '7days', '30days', or 'all'
        
        Returns:
            List of dicts with 'period' (time label) and 'count' (workflow executions)
        """
        now = datetime.now(timezone.utc)
        
        # Determine cutoff date and format based on time range
        if time_range == "today":
            cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            date_format = "%Y-%m-%d %H:00"  # Hourly for today
            group_key = "hour"
        elif time_range == "7days":
            cutoff_date = now - timedelta(days=7)
            date_format = "%Y-%m-%d"  # Daily for 7 days
            group_key = "date"
        elif time_range == "30days":
            cutoff_date = now - timedelta(days=30)
            date_format = "%Y-%m-%d"  # Daily for 30 days
            group_key = "date"
        else:  # all
            # Get earliest run to determine span
            earliest = self.collection.find_one(sort=[("run_context.started_at", pymongo.ASCENDING)])
            if earliest:
                earliest_time = earliest.get("run_context", {}).get("started_at")
                if earliest_time:
                    try:
                        if isinstance(earliest_time, str):
                            # Parse as timezone-aware datetime
                            cutoff_date = datetime.fromisoformat(earliest_time.replace('Z', '+00:00'))
                            # Ensure it's UTC timezone-aware
                            if cutoff_date.tzinfo is None:
                                cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
                        else:
                            # Convert timestamp to timezone-aware datetime
                            cutoff_date = datetime.fromtimestamp(earliest_time, tz=timezone.utc)
                    except (ValueError, TypeError):
                        cutoff_date = now - timedelta(days=365)  # Default to 1 year
                else:
                    cutoff_date = now - timedelta(days=365)
            else:
                cutoff_date = now - timedelta(days=365)
            
            # Ensure cutoff_date is timezone-aware for comparison
            if cutoff_date.tzinfo is None:
                cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
            
            # Use weekly grouping for all time if span > 90 days, otherwise daily
            span_days = (now - cutoff_date).days
            if span_days > 90:
                date_format = "%Y-%m-%d"  # Weekly would be better but daily is simpler
                group_key = "date"
            else:
                date_format = "%Y-%m-%d"
                group_key = "date"
        
        # Convert to ISO format string for MongoDB query
        cutoff_iso = cutoff_date.isoformat().replace('+00:00', 'Z')
        
        pipeline = [
            {"$match": {
                "run_context.started_at": {"$gte": cutoff_iso}
            }},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": date_format,
                        "date": {"$dateFromString": {"dateString": "$run_context.started_at"}}
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        try:
            results = list(self.collection.aggregate(pipeline))
            return [{"period": doc["_id"], "count": doc["count"]} for doc in results]
        except Exception:
            return []


@analytics_bp.route("/overview", methods=["GET"])
@from_query({
    "time_range": fields.Str(data_key="time_range", load_default="all", validate=lambda x: x in ["today", "7days", "30days", "all"])
})
def get_overview(time_range):
    """
    Get comprehensive overview of all analytics.
    
    Returns all key metrics in a single request for the dashboard.
    Uses in-memory caching to reduce database load.
    
    Query params:
        time_range (str): Time range filter - 'today', '7days', '30days', or 'all' (default: 'all')
    """
    try:
        # Check if cache is still valid (cache key includes time_range)
        current_time = time.time()
        cache_key = time_range
        
        if (_analytics_cache.get('data') is not None and 
            _analytics_cache.get('cache_key') == cache_key and
            current_time - _analytics_cache['timestamp'] < _analytics_cache['ttl']):
            # Return cached data
            return jsonify(_analytics_cache['data']), 200
        
        # Cache miss or expired - fetch fresh data
        analytics = WorkflowAnalytics(MONGO_URI, MONGO_DB)
        
        overview = {
            "total_stats": analytics.get_total_stats(),
            "status_breakdown": analytics.get_status_breakdown(),
            "time_stats": analytics.get_time_based_stats(),
            "active_today": analytics.get_active_users_today(),
            "active_7days": analytics.get_active_users(days=7),
            "active_30days": analytics.get_active_users(days=30),
            "top_users": analytics.get_user_activity(limit=10),
            "top_blueprints": analytics.get_blueprint_usage(limit=10, time_range=time_range),
            "time_series": analytics.get_time_series_activity(time_range=time_range),
            "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        # Update cache
        _analytics_cache['data'] = overview
        _analytics_cache['timestamp'] = current_time
        _analytics_cache['cache_key'] = cache_key
        
        return jsonify(overview), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/users/active", methods=["GET"])
@from_query({
    "days": fields.Int(data_key="days", load_default=7)
})
def get_active_users(days):
    """
    Get active users for the specified number of days.
    
    Query params:
        days (int): Number of days to look back (default: 7)
    """
    try:
        analytics = WorkflowAnalytics(MONGO_URI, MONGO_DB)
        active_users = analytics.get_active_users(days=days)
        
        return jsonify({
            "days": days,
            "active_users": active_users,
            "count": len(active_users)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/users/activity", methods=["GET"])
@from_query({
    "limit": fields.Int(data_key="limit", load_default=15)
})
def get_user_activity(limit):
    """
    Get detailed user activity breakdown.
    
    Query params:
        limit (int): Number of top users to return (default: 15)
    """
    try:
        analytics = WorkflowAnalytics(MONGO_URI, MONGO_DB)
        user_activity = analytics.get_user_activity(limit=limit)
        
        return jsonify({
            "user_activity": user_activity,
            "count": len(user_activity)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/blueprints/usage", methods=["GET"])
@from_query({
    "limit": fields.Int(data_key="limit", load_default=10)
})
def get_blueprint_usage(limit):
    """
    Get most used blueprints.
    
    Query params:
        limit (int): Number of top blueprints to return (default: 10)
    """
    try:
        analytics = WorkflowAnalytics(MONGO_URI, MONGO_DB)
        blueprint_usage = analytics.get_blueprint_usage(limit=limit)
        
        return jsonify({
            "blueprint_usage": blueprint_usage,
            "count": len(blueprint_usage)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/activity/hourly", methods=["GET"])
@from_query({
    "days": fields.Int(data_key="days", load_default=7)
})
def get_hourly_activity(days):
    """
    Get hourly activity distribution.
    
    Query params:
        days (int): Number of days to look back (default: 7)
    """
    try:
        analytics = WorkflowAnalytics(MONGO_URI, MONGO_DB)
        hourly_activity = analytics.get_hourly_activity(days=days)
        
        return jsonify({
            "days": days,
            "hourly_activity": hourly_activity
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

