from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import json

from rich.console import Console
from rich.table import Table

from soma.cogs.self_notes.notes import SelfNotes
from soma.sandbox import make_env, ACTIONS
from .state import StateSnapshot
from .events import JsonlEventLog
from .store import EventStore


console = Console()


def _select_action(seed: int) -> str:
    # Deterministic: map the LCG seed to one of the ACTIONS
    return ACTIONS[seed % len(ACTIONS)]


def run_loop(ticks: int, seed: int, run_dir: Path, run_id: str, env_name: str = "grid-v0") -> None:
    """Run the SOMA loop for `ticks` steps with a minimal sandbox.

    Artifacts in `run_dir`:
      - meta.json
      - events.jsonl
      - events.sqlite
    """
    meta = {
        "phase": "M2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticks": ticks,
        "seed": seed,
        "run_id": run_id,
        "env": env_name,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    event_log = JsonlEventLog(run_dir / "events.jsonl")
    store = EventStore(db_path=run_dir / "events.sqlite", run_id=run_id)
    notes = SelfNotes(event_log=event_log, store=store)

    env = make_env(env_name, size=9, n_objects=12, view_radius=1)

    # Initial reset observation
    state = StateSnapshot(tick=0, rng_seed=seed, info={})
    obs0 = env.reset(seed)
    event_log.write({"type": "obs", "tick": state.tick, "obs": obs0})
    store.write(event_type="obs", tick=state.tick, payload=obs0)
    notes.note(kind="startup", payload={"message": "system alive", "env": env_name}, tick=state.tick)

    table = Table(title="SOMA M2 — GridWorld v0")
    table.add_column("Tick")
    table.add_column("Action")
    table.add_column("Seen (uniq)")
    table.add_column("Pos")

    for _ in range(ticks):
        action = _select_action(state.rng_seed)
        obs, info = env.step(action)

        summary = {
            "pos": obs["agent"],
            "unique": obs["summary"]["unique"],
        }

        event: Dict[str, Any] = {
            "type": "tick",
            "tick": state.tick,
            "rng_seed": state.rng_seed,
            "action": action,
            "summary": summary,
        }
        event_log.write(event)
        store.write(event_type="tick", tick=state.tick, payload=event)

        # Occasional note when the agent pings or every 6 ticks
        if action == "ping" or state.tick % 6 == 0:
            notes.note(kind="perception", payload={"unique": summary["unique"]}, tick=state.tick)

        table.add_row(str(state.tick), action, ",".join(summary["unique"]) or "-", f"({summary['pos']['x']},{summary['pos']['y']})")

        state = state.next()

    notes.note(kind="shutdown", payload={"ticks": ticks}, tick=state.tick)

    console.print(table)

    # Clean up
    event_log.close()
    store.close()