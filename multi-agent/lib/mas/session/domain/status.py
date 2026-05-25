from enum import Enum


class SessionStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    # Shared-session specific busy statuses:
    # LOCKED   – session is reserved / queued for execution by another caller
    # IN_USE   – session is actively being executed by another caller
    LOCKED = "LOCKED"
    IN_USE = "IN_USE"
