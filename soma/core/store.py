from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import sqlite3
import json
from datetime import datetime, timezone


class EventStore:
    """SQLite-backed append-only event store.

    Table schema (created on first use):
      events(id INTEGER PK, ts TEXT, run_id TEXT, tick INTEGER, type TEXT, data TEXT)
    """

    def __init__(self, db_path: Path, run_id: str):
        self.db_path = Path(db_path)
        self.run_id = run_id
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              run_id TEXT NOT NULL,
              tick INTEGER NOT NULL,
              type TEXT NOT NULL,
              data TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_run_tick ON events(run_id, tick)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        self.conn.commit()

    def write(self, event_type: str, tick: int, payload: Dict[str, Any]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        data = json.dumps(payload, ensure_ascii=False)
        self.conn.execute(
            "INSERT INTO events(ts, run_id, tick, type, data) VALUES(?,?,?,?,?)",
            (ts, self.run_id, tick, event_type, data),
        )
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass