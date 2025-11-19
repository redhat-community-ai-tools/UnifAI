
## Slack Events

Simple, explicit pattern to handle Slack Events in one place.

### Quick start
1) Implement a handler class for an event type  
2) Register the handler with `SlackEventService`  
3) Dispatch incoming payloads to the service

### 1) Implement a handler
Create a class with an `event_type` and `handle(payload)`:

```python
from typing import Dict, Any
from services.slack_events.event_handler import SlackEventHandler
from services.slack_events.slack_event_models import ChannelCreatedEvent

class ChannelCreatedEventHandler(SlackEventHandler):
    event_type = "channel_created"

    def handle(self, payload: Dict[str, Any]) -> None:
        typed = ChannelCreatedEvent.from_payload(payload)
        if typed.type != self.event_type or not typed.channel_id:
            return
        # Persist or process as needed using typed.channel_raw and typed.event_ts
```

Optional: use small helpers like `resolve_event_time(payload)` if convenient.

### 2) Register the handler and 3) Dispatch payloads
Do this where your events arrive (e.g., Celery task or API endpoint):

```python
from services.slack_events.slack_events_service import SlackEventService
from services.slack_events.handlers.channel_created_handler import ChannelCreatedEventHandler

event_service = SlackEventService()
event_service.register_class(ChannelCreatedEventHandler)

# Later, when a Slack payload comes in:
event_service.dispatch(payload)  # returns True if a handler ran
```

### Typed event models (optional)
Typed models make payload parsing explicit per event:

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class ChannelCreatedEvent:
    type: str
    event_ts: Optional[str]
    channel_id: str
    channel_name: str
    is_private: bool
    channel_raw: Dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ChannelCreatedEvent":
        e = payload.get("event") or {}
        ch = e.get("channel") or {}
        return cls(
            type=e.get("type"),
            event_ts=e.get("event_ts"),
            channel_id=ch.get("id"),
            channel_name=ch.get("name"),
            is_private=bool(ch.get("is_private", False)),
            channel_raw=ch,
        )
```

### Adding more events
- Create a handler with `event_type = "<slack-event-type>"`.
- Optionally add a typed model with `.from_payload()`.
- Call `event_service.register_class(YourHandler)`.

That’s it. Keep handlers small, explicit, and event-specific.*** End Patch*** }``` ***!