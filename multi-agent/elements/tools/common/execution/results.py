"""
Result types for tool execution.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from datetime import datetime


@dataclass
class ToolExecutionResult:
    """Result of a single tool execution."""
    tool_name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_error(self) -> bool:
        """Check if execution had an error."""
        return self.error is not None or not self.success
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"ToolExecutionResult({self.tool_name}: {status}, {self.execution_time:.3f}s)"


@dataclass 
class BatchExecutionResult:
    """Result of batch tool execution."""
    results: List[ToolExecutionResult]
    total_time: float
    mode: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def all_successful(self) -> bool:
        """Check if all executions were successful."""
        return all(r.success for r in self.results)
    
    @property
    def failed_count(self) -> int:
        """Count of failed executions."""
        return sum(1 for r in self.results if not r.success)
    
    @property
    def success_count(self) -> int:
        """Count of successful executions."""
        return sum(1 for r in self.results if r.success)
    
    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if not self.results:
            return 0.0
        return (self.success_count / len(self.results)) * 100
    
    def __str__(self) -> str:
        return (
            f"BatchExecutionResult({len(self.results)} tools, "
            f"{self.success_count} success, {self.failed_count} failed, "
            f"{self.total_time:.3f}s, {self.mode})"
        )


@dataclass
class ExecutionMetrics:
    """Metrics for tool execution tracking."""
    total_executions: int = 0
    total_errors: int = 0
    total_time: float = 0.0
    average_execution_time: float = 0.0
    error_rate: float = 0.0
    
    def update(self, result: ToolExecutionResult) -> None:
        """Update metrics with a new result."""
        self.total_executions += 1
        self.total_time += result.execution_time
        
        if not result.success:
            self.total_errors += 1
        
        # Calculate derived metrics
        self.average_execution_time = self.total_time / self.total_executions
        self.error_rate = (self.total_errors / self.total_executions) * 100 if self.total_executions > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_executions": self.total_executions,
            "total_errors": self.total_errors,
            "total_time": self.total_time,
            "average_execution_time": self.average_execution_time,
            "error_rate": self.error_rate
        }

