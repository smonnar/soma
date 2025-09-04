from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any


def _view_key(summary: Dict[str, Any]) -> Tuple[Tuple[str, int], ...]:
    counts = summary.get("counts", {}) or {}
    items = []
    for k, v in counts.items():
        try:
            items.append((str(k), int(v)))
        except Exception:
            items.append((str(k), 0))
    items.sort(key=lambda t: t[0])
    return tuple(items)


def _neighbors(pos: Tuple[int, int], size: int) -> Dict[str, Tuple[int, int]]:
    x, y = pos
    nb: Dict[str, Tuple[int, int]] = {}
    if y > 0:
        nb["up"] = (x, y - 1)
    if y < size - 1:
        nb["down"] = (x, y + 1)
    if x > 0:
        nb["left"] = (x - 1, y)
    if x < size - 1:
        nb["right"] = (x + 1, y)
    return nb


@dataclass
class StalenessState:
    novelty_ema: float = 1.0
    noop_streak: int = 0
    repeat_view_streak: int = 0
    last_view: Tuple[Tuple[str, int], ...] | None = None
    last_pos: Tuple[int, int] | None = None


class StalenessMonitor:
    """Tracks staleness/boredom and a visited heatmap.

    Call order each tick:
      1) boredom = pre(summary, novelty, pos)
      2) ... choose action, step env ...
      3) post(action_final, pos_next)
    """

    def __init__(self, size: int, *, alpha: float = 0.2, novelty_low: float = 0.15, max_noop: int = 5, max_repeat: int = 5) -> None:
        self.size = int(size)
        self.alpha = float(alpha)
        self.novelty_low = float(novelty_low)
        self.max_noop = int(max_noop)
        self.max_repeat = int(max_repeat)
        self.state = StalenessState()
        self.visited: Dict[Tuple[int, int], int] = {}

    # ------------------ metrics ------------------
    def pre(self, summary: Dict[str, Any], novelty: float, pos: Tuple[int, int]) -> Dict[str, float | int]:
        s = self.state
        # novelty EMA
        s.novelty_ema = (1.0 - self.alpha) * s.novelty_ema + self.alpha * float(max(0.0, min(1.0, novelty)))
        # repeat view streak
        key = _view_key(summary)
        if s.last_view is not None and key == s.last_view:
            s.repeat_view_streak += 1
        else:
            s.repeat_view_streak = 0
        s.last_view = key
        # ensure current position has a count (for least-visited computation stability)
        self.visited.setdefault(pos, 0)
        # boredom combines low-novelty, noop streak, and repeat views
        b = 0.0
        b += 0.5 * max(0.0, 1.0 - s.novelty_ema)  # low novelty → higher boredom
        b += 0.25 * min(1.0, s.noop_streak / max(1, self.max_noop))
        b += 0.25 * min(1.0, s.repeat_view_streak / max(1, self.max_repeat))
        boredom = max(0.0, min(1.0, b))
        return {
            "novelty_ema": s.novelty_ema,
            "noop_streak": s.noop_streak,
            "repeat_view_streak": s.repeat_view_streak,
            "boredom": boredom,
        }

    def post(self, action_final: str, pos_next: Tuple[int, int]) -> None:
        # noop streak
        if action_final == "noop":
            self.state.noop_streak += 1
        else:
            self.state.noop_streak = 0
        # visited heatmap
        self.visited[pos_next] = self.visited.get(pos_next, 0) + 1
        self.state.last_pos = pos_next

    def least_visited_dirs(self, pos: Tuple[int, int]) -> List[str]:
        nb = _neighbors(pos, self.size)
        if not nb:
            return []
        # Get min visit count among neighbors
        counts = {d: self.visited.get(p, 0) for d, p in nb.items()}
        if not counts:
            return []
        m = min(counts.values())
        # Return directions sorted from least to most visited
        return [d for d, c in sorted(counts.items(), key=lambda kv: (kv[1], kv[0])) if c == m]