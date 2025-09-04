from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Tuple
import json


class StateTracker:
    """Keep a compact, human-readable snapshot of SOMA's internal state.

    Files:
      - state.json  : latest snapshot
      - state.jsonl : append-only history of snapshots (one per tick)
    """

    def __init__(self, run_dir: Path, keep: int = 128) -> None:
        self.run_dir = Path(run_dir)
        self.keep = int(keep)
        self.history: Deque[Dict[str, Any]] = deque(maxlen=keep)
        self._state_path = self.run_dir / "state.json"
        self._hist_path = self.run_dir / "state.jsonl"

    def _snapshot(
        self,
        *,
        tick: int,
        drive: str,
        behavior: str,
        action: str,
        novelty: float,
        boredom: float,
        coverage: float,
        matches: List[Tuple[int, float]] | None,
        attention: List[str] | None,
        reflex: List[str] | None,
    ) -> Dict[str, Any]:
        recall_top = None
        if matches:
            t0, s0 = matches[0]
            recall_top = {"tick": int(t0), "score": float(s0)}
        return {
            "tick": int(tick),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "drive": str(drive),
            "behavior": str(behavior),
            "action": str(action),
            "novelty": float(novelty),
            "boredom": float(boredom),
            "coverage": float(coverage),
            "recall_top": recall_top,
            "attention": list(attention or []),
            "reflex": list(reflex or []),
        }

    def update(self, **kwargs: Any) -> Dict[str, Any]:
        snap = self._snapshot(**kwargs)
        self.history.append(snap)
        # Write current snapshot
        self._state_path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        # Append to history
        with self._hist_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap) + "\n")
        return snap