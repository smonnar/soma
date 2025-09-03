from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
import json

from rich.console import Console
from rich.table import Table

from soma.cogs.self_notes.notes import SelfNotes
from soma.cogs.reflex.reflex import ReflexManager
from soma.sandbox import make_env, ACTIONS
from .state import StateSnapshot
from .events import JsonlEventLog
from .store import EventStore


console = Console()


def _select_action(seed: int) -> str:
    # Deterministic: map the LCG seed to one of the ACTIONS
    return ACTIONS[seed % len(ACTIONS)]


def run_loop(
    ticks: int,
    seed: int,
    run_dir: Path,
    run_id: str,
    env_name: str = "grid-v0",
    size: int = 9,
    n_objects: int = 12,
    view_radius: int = 1,
) -> None:
    """Run the SOMA loop for `ticks` steps with sandbox + reflex manager (M3)."""
    meta = {
        "phase": "M3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticks": ticks,
        "seed": seed,
        "run_id": run_id,
        "env": {"name": env_name, "size": size, "n_objects": n_objects, "view_radius": view_radius},
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    event_log = JsonlEventLog(run_dir / "events.jsonl")
    store = EventStore(db_path=run_dir / "events.sqlite", run_id=run_id)
    notes = SelfNotes(event_log=event_log, store=store)
    reflex = ReflexManager(notes=notes, overload_unique_threshold=4)

    env = make_env(env_name, size=size, n_objects=n_objects, view_radius=view_radius)

    # Initial reset observation
    state = StateSnapshot(tick=0, rng_seed=seed, info={})
    obs0 = env.reset(seed)
    event_log.write({"type": "obs", "tick": state.tick, "obs": obs0})
    store.write(event_type="obs", tick=state.tick, payload=obs0)
    notes.note(kind="startup", payload={"message": "system alive", "env": env_name}, tick=state.tick)

    table = Table(title="SOMA M3 — GridWorld v0 + Reflexes")
    table.add_column("Tick")
    table.add_column("Action")
    table.add_column("Reflex")
    table.add_column("Seen (uniq)")
    table.add_column("Pos")

    for _ in range(ticks):
        selected = _select_action(state.rng_seed)

        # Derive view features *before* action (current observation context)
        # We use the latest view from obs0 on tick 0, and then after each step, obs becomes next state.
        # To keep code compact, we step first using the selected action and then compute summary from returned obs.
        obs, info = env.step(selected)
        unique: List[str] = obs["summary"]["unique"]

        # Reflex may override based on the *post-step* observation and selected action
        # (Design choice: simple but yields visible effects quickly.)
        final_action, triggers = reflex.advise(tick=state.tick, selected=selected, unique_tokens=unique)

        # If override occurred and changed final action meaningfully, we could apply side-effects.
        # In v1 we'll just record the override; future M3.1 can re-step if needed.

        event: Dict[str, Any] = {
            "type": "tick",
            "tick": state.tick,
            "rng_seed": state.rng_seed,
            "action_selected": selected,
            "action_final": final_action,
            "reflex": triggers,
            "summary": {"pos": obs["agent"], "unique": unique},
        }
        event_log.write(event)
        store.write(event_type="tick", tick=state.tick, payload=event)

        table.add_row(
            str(state.tick),
            final_action,
            ",".join(triggers) or "-",
            ",".join(unique) or "-",
            f"({obs['agent']['x']},{obs['agent']['y']})",
        )

        state = state.next()

    notes.note(kind="shutdown", payload={"ticks": ticks}, tick=state.tick)

    console.print(table)

    # Clean up
    event_log.close()
    store.close()