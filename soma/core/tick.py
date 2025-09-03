from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import json

from rich.console import Console
from rich.table import Table

from soma.cogs.self_notes.notes import SelfNotes
from .state import StateSnapshot
from .events import JsonlEventLog
from .store import EventStore


console = Console()


def run_loop(ticks: int, seed: int, run_dir: Path, run_id: str) -> None:
    """Run the SOMA loop for `ticks` steps (M1: with SQLite store + self-notes).

    Artifacts in `run_dir`:
      - meta.json
      - events.jsonl
      - events.sqlite
    """
    meta = {
        "phase": "M1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticks": ticks,
        "seed": seed,
        "run_id": run_id,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    event_log = JsonlEventLog(run_dir / "events.jsonl")
    store = EventStore(db_path=run_dir / "events.sqlite", run_id=run_id)
    notes = SelfNotes(event_log=event_log, store=store)

    state = StateSnapshot(tick=0, rng_seed=seed, info={})

    table = Table(title="SOMA M1 — Hello Tick + Store + Notes")
    table.add_column("Tick")
    table.add_column("Seed")
    table.add_column("Notes")

    # Initial self-note
    notes.note(kind="startup", payload={"message": "system alive"}, tick=state.tick)

    for _ in range(ticks):
        note = f"tick {state.tick}: system alive"
        event: Dict[str, Any] = {
            "type": "tick",
            "tick": state.tick,
            "rng_seed": state.rng_seed,
            "note": note,
        }
        event_log.write(event)
        store.write(event_type="tick", tick=state.tick, payload=event)
        table.add_row(str(state.tick), str(state.rng_seed), note)

        # Periodic self-note (every 5 ticks)
        if state.tick % 5 == 0 and state.tick > 0:
            notes.note(kind="heartbeat", payload={"tick": state.tick}, tick=state.tick)

        state = state.next()

    notes.note(kind="shutdown", payload={"ticks": ticks}, tick=state.tick)

    console.print(table)

    # Clean up
    event_log.close()
    store.close()