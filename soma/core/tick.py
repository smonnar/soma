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
from soma.cogs.perception.features import extract_features
from soma.cogs.perception.embedder import PerceptionEmbedderV2
from soma.cogs.working_memory.staleness import StalenessMonitor
from soma.cogs.state_tracker.tracker import StateTracker
from soma.cogs.channel.symbolic import SymbolicChannel  # <-- NEW
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
    """Run SOMA with Perception V2 + Staleness/Boredom + Planner + State + Channel (M9)."""
    meta = {
        "phase": "M9-channel",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticks": ticks,
        "seed": seed,
        "run_id": run_id,
        "env": {"name": env_name, "size": size, "n_objects": n_objects, "view_radius": view_radius},
        "perception": {"embedder": "v2", "dim": 64},
        "memory": {"dim": 64, "max_items": 512},
        "channel": {"version": "v0", "vocab": list(SymbolicChannel.encode.__annotations__) if False else None},
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    event_log = JsonlEventLog(run_dir / "events.jsonl")
    store = EventStore(db_path=run_dir / "events.sqlite", run_id=run_id)
    notes = SelfNotes(event_log=event_log, store=store)
    reflex = ReflexManager(notes=notes, overload_unique_threshold=5)
    memory = MemorySystem(dim=64, max_items=512)
    curiosity = CuriosityEngine(notes=notes, novelty_threshold=0.6, change_threshold=0.5, top_k=3)
    motivation = MotivationManager(notes=notes)
    planner = BehaviorPlanner()
    embedder = PerceptionEmbedderV2(dim=64)
    stale = StalenessMonitor(size=size, alpha=0.2, novelty_low=0.15, max_noop=5, max_repeat=5)
    tracker = StateTracker(run_dir=run_dir, keep=128)
    channel = SymbolicChannel(notes=notes)  # <-- NEW

    env = make_env(env_name, size=size, n_objects=n_objects, view_radius=view_radius)

    # Initial reset observation
    state = StateSnapshot(tick=0, rng_seed=seed, info={})
    obs = env.reset(seed)
    event_log.write({"type": "obs", "tick": state.tick, "obs": obs})
    store.write(event_type="obs", tick=state.tick, payload=obs)
    notes.note(kind="startup", payload={"message": "system alive", "env": env_name}, tick=state.tick)

    table = Table(title="SOMA M9 — Grid + PerceptionV2 + Staleness + State + Channel")
    table.add_column("Tick")
    table.add_column("Drive")
    table.add_column("Behavior")
    table.add_column("Act")
    table.add_column("Bored")
    table.add_column("Novelty")
    table.add_column("Sym")
    table.add_column("Pos")

    for _ in range(ticks):
        # --- Perception V2: features + embedding ---
        feats = extract_features(obs, grid_size=size)
        vec = embedder.embed(feats)
        matches: List[Tuple[int, float]] = memory.query(vec, top_k=3, min_score=0.5)

        # Curiosity on current view using matches
        cur = curiosity.assess(tick=state.tick, summary=obs["summary"], matches=matches, memory=memory)

        # Store vectorized perception for future recall
        memory.add_vector(tick=state.tick, vector=vec, meta={"features": feats, "attention": cur.get("attention", [])})

        # --- Staleness / boredom (pre-action) ---
        pos_now = (obs["agent"]["x"], obs["agent"]["y"])
        st = stale.pre(summary=obs["summary"], novelty=float(cur["novelty"]), pos=pos_now)
        boredom = float(st["boredom"])  # 0..1

        # --- Motivation update ---
        drives = motivation.update(tick=state.tick, curiosity=cur, matches=matches, reflex_triggers=[], boredom=boredom)
        dominant = max(drives.items(), key=lambda kv: kv[1])[0]

        # --- Planner proposes behavior + action (bias by least-visited) ---
        least_dirs = stale.least_visited_dirs(pos_now)
        behavior, selected = planner.propose(
            tick=state.tick,
            rng_seed=state.rng_seed,
            dominant=dominant,
            curiosity=cur,
            matches=matches,
            pos=pos_now,
            least_visited=least_dirs,
            boredom=boredom,
        )

        # --- Reflex may override BEFORE stepping ---
        unique_before: List[str] = obs["summary"]["unique"]
        final_action, triggers = reflex.advise(tick=state.tick, selected=selected, unique_tokens=unique_before)
        if triggers:
            drives = motivation.update(tick=state.tick, curiosity=cur, matches=matches, reflex_triggers=triggers, boredom=boredom)
            dominant = max(drives.items(), key=lambda kv: kv[1])[0]

        # --- Channel emission (pre-step, based on current view & decisions) ---
        tokens, gloss = channel.maybe_emit(
            tick=state.tick,
            novelty=float(cur["novelty"]),
            boredom=boredom,
            matches=matches,
            summary=obs["summary"],
            drives=drives,
            dominant=dominant,
            noop_streak=int(st["noop_streak"]),
            reflex_triggers=triggers,
        )

        # Step
        obs_next, info = env.step(final_action)
        pos_next = (obs_next["agent"]["x"], obs_next["agent"]["y"])

        # Post-action staleness updates (noop streak, visited)
        stale.post(action_final=final_action, pos_next=pos_next)

        # Coverage after moving
        coverage = len(stale.visited) / float(size * size)

        # --- State snapshot update ---
        snapshot = tracker.update(
            tick=state.tick,
            drive=dominant,
            behavior=behavior,
            action=final_action,
            novelty=float(cur["novelty"]),
            boredom=boredom,
            coverage=coverage,
            matches=matches,
            attention=list(cur.get("attention", [])),
            reflex=triggers,
        )

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
            "staleness": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()},
            "perception": {"features": feats},
            "state": snapshot,
            "channel": {"tokens": tokens, "gloss": gloss},
            "view_after": {"unique": obs_next["summary"]["unique"], "pos": obs_next["agent"]},
        }
        event_log.write(event)
        store.write(event_type="tick", tick=state.tick, payload=event)

        table.add_row(
            str(state.tick),
            {"curiosity": "Cur", "stability": "Stab", "pattern_completion": "Pat", "truth_seeking": "Truth", "caregiver_alignment": "Care", "overload_regulation": "Over"}.get(dominant, dominant),
            behavior,
            final_action,
            f"{boredom:.2f}",
            f"{float(cur['novelty']):.2f}",
            (" ".join(tokens) if tokens else "-"),
            f"({obs_next['agent']['x']},{obs_next['agent']['y']})",
        )

        obs = obs_next
        state = state.next()

    notes.note(kind="shutdown", payload={"ticks": ticks}, tick=state.tick)

    console.print(table)

    event_log.close()
    store.close()