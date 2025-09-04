from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json

from rich.console import Console
from rich.table import Table

from soma.cogs.self_notes.notes import SelfNotes
from soma.cogs.reflex.reflex import ReflexManager
from soma.cogs.memory.memory import MemorySystem
from soma.cogs.curiosity.curiosity import CuriosityEngine
from soma.cogs.motivation.motivation import MotivationManager
from soma.cogs.planner.planner import BehaviorPlanner
from soma.sandbox import make_env
from .state import StateSnapshot
from .events import JsonlEventLog
from .store import EventStore


console = Console()


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
    """Run SOMA with sandbox + reflexes + memory + curiosity + motivation + planner (M7)."""
    meta = {
        "phase": "M7",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticks": ticks,
        "seed": seed,
        "run_id": run_id,
        "env": {"name": env_name, "size": size, "n_objects": n_objects, "view_radius": view_radius},
        "memory": {"dim": 64, "max_items": 512},
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    event_log = JsonlEventLog(run_dir / "events.jsonl")
    store = EventStore(db_path=run_dir / "events.sqlite", run_id=run_id)
    notes = SelfNotes(event_log=event_log, store=store)
    reflex = ReflexManager(notes=notes, overload_unique_threshold=4)
    memory = MemorySystem(dim=64, max_items=512)
    curiosity = CuriosityEngine(notes=notes, novelty_threshold=0.6, change_threshold=0.5, top_k=3)
    motivation = MotivationManager(notes=notes)
    planner = BehaviorPlanner()

    env = make_env(env_name, size=size, n_objects=n_objects, view_radius=view_radius)

    # Initial reset observation
    state = StateSnapshot(tick=0, rng_seed=seed, info={})
    obs = env.reset(seed)
    event_log.write({"type": "obs", "tick": state.tick, "obs": obs})
    store.write(event_type="obs", tick=state.tick, payload=obs)
    notes.note(kind="startup", payload={"message": "system alive", "env": env_name}, tick=state.tick)

    table = Table(title="SOMA M7 — Grid + Reflex + Memory + Curiosity + Motivation + Planner")
    table.add_column("Tick")
    table.add_column("Drive")
    table.add_column("Behavior")
    table.add_column("Act")
    table.add_column("Reflex")
    table.add_column("Novelty")
    table.add_column("Attention")
    table.add_column("Pos")

    for _ in range(ticks):
        # --- Recall & curiosity on current view (pre-action) ---
        vec = memory.embed(obs["summary"])  # normalized vector
        matches: List[Tuple[int, float]] = memory.query(vec, top_k=3, min_score=0.5)  # higher threshold
        cur = curiosity.assess(tick=state.tick, summary=obs["summary"], matches=matches, memory=memory)

        # Add current observation to memory for future use
        memory.add(tick=state.tick, summary=obs["summary"], action=None)

        # --- Motivation update (before action) ---
        drives = motivation.update(tick=state.tick, curiosity=cur, matches=matches, reflex_triggers=[])
        dominant = max(drives.items(), key=lambda kv: kv[1])[0]

        # --- Planner proposes behavior + action ---
        pos = (obs["agent"]["x"], obs["agent"]["y"])
        behavior, selected = planner.propose(
            tick=state.tick,
            rng_seed=state.rng_seed,
            dominant=dominant,
            curiosity=cur,
            matches=matches,
            pos=pos,
        )

        # --- Reflex may override BEFORE stepping ---
        unique_before: List[str] = obs["summary"]["unique"]
        final_action, triggers = reflex.advise(tick=state.tick, selected=selected, unique_tokens=unique_before)

        # If reflex fired, update motivation once more
        if triggers:
            drives = motivation.update(tick=state.tick, curiosity=cur, matches=matches, reflex_triggers=triggers)
            dominant = max(drives.items(), key=lambda kv: kv[1])[0]

        # Step using the final action
        obs_next, info = env.step(final_action)

        event: Dict[str, Any] = {
            "type": "tick",
            "tick": state.tick,
            "rng_seed": state.rng_seed,
            "planner": {"behavior": behavior, "action_proposed": selected},
            "action_final": final_action,
            "reflex": triggers,
            "curiosity": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in cur.items()},
            "recall": [{"tick": t, "score": round(s, 6)} for t, s in matches],
            "motivation": {"drives": {k: round(v, 3) for k, v in drives.items()}, "dominant": dominant},
            "view_before": {"unique": unique_before, "pos": obs["agent"]},
            "view_after": {"unique": obs_next["summary"]["unique"], "pos": obs_next["agent"]},
        }
        event_log.write(event)
        store.write(event_type="tick", tick=state.tick, payload=event)

        short = {
            "curiosity": "Cur",
            "stability": "Stab",
            "pattern_completion": "Pat",
            "truth_seeking": "Truth",
            "caregiver_alignment": "Care",
            "overload_regulation": "Over",
        }.get(dominant, dominant)

        table.add_row(
            str(state.tick),
            short,
            behavior,
            final_action,
            ",".join(triggers) or "-",
            f"{float(cur['novelty']):.2f}",
            ",".join(cur["attention"]) if cur["attention"] else "-",
            f"({obs_next['agent']['x']},{obs_next['agent']['y']})",
        )

        obs = obs_next
        state = state.next()

    notes.note(kind="shutdown", payload={"ticks": ticks}, tick=state.tick)

    console.print(table)

    event_log.close()
    store.close()