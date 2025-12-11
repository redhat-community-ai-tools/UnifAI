"""
Analytics utility functions.

Contains helper functions for working with WorkflowAnalytics.
"""

from utils.analytics.workflow_analytics import WorkflowAnalytics


def get_workflow_analytics() -> WorkflowAnalytics:
    """Get a WorkflowAnalytics instance with default configuration."""
    return WorkflowAnalytics()

