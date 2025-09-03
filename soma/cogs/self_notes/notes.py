from __future__ import annotations

from typing import Any, Dict, Optional

from soma.core.events import JsonlEventLog
from soma.core.store import EventStore


class SelfNotes:
    """Structured self-notes that write to both JSONL and SQLite."""

    def __init__(self, event_log: JsonlEventLog, store: EventStore):
        self.event_log = event_log
        self.store = store

    def note(self, kind: str, payload: Dict[str, Any], tick: Optional[int] = None) -> None:
        event = {"type": "note", "kind": kind, "payload": payload}
        if tick is not None:
            event["tick"] = tick
        self.event_log.write(event)
        self.store.write(event_type="note", tick=tick or -1, payload=event)