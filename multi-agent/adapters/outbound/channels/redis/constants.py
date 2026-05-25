from enum import StrEnum

STREAM_PREFIX = "mas:stream:"
ACTIVE_SESSIONS_KEY = "mas:sessions:active"
CANCEL_GATE_PREFIX = "mas:stream_gate:"


class StreamField(StrEnum):
    PAYLOAD = "payload"
    CONTROL = "__control"


class ControlSignal(StrEnum):
    CLOSE = "close"
