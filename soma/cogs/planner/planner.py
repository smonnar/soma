from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

ACTIONS = ["noop", "up", "down", "left", "right", "ping"]
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
DIR_CYCLE = ["up", "right", "down", "left"]


class BehaviorPlanner:
    """
    Drive → behavior → action with:
      - Curiosity: prefer least-visited directions (exploration bias).
      - Stability: prefer most-visited directions (settling bias).
      - Truth-seeking: simple probe policy using 'ping'.
      - Pattern-completion: simple revisit sweep (alternating L/R).
    """

    def __init__(self) -> None:
        self.recent_pos: Deque[Tuple[int, int]] = deque(maxlen=8)
        self.last_action: Optional[str] = None
        self._alt = False  # used by pattern-completion sweep

    def propose(
        self,
        *,
        tick: int,
        rng_seed: int,
        dominant: str,
        curiosity: Dict[str, float | List[str]],
        matches: List[Tuple<int, float]],
        pos: Tuple[int, int],
        least_visited: List[str],
        boredom: float,
        explore_pressure: float = 0.0,
        settle_pressure: float = 0.0,
    ) -> Tuple[str, str]:
        """
        Return (behavior, action).
        - `least_visited`: ordered best → worst directions for exploration.
        - `boredom`: 0..1 scalar from staleness monitor.
        """
        self.recent_pos.append(pos)
        b = float(boredom)
        ep = float(explore_pressure)
        sp = float(settle_pressure)

        def choose_cycle() -> str:
            base = (int(rng_seed) + int(tick)) % 4
            for i in range(4):
                cand = DIR_CYCLE[(base + i) % 4]
                # avoid immediate backtrack if possible
                if self.last_action and OPPOSITE.get(self.last_action) == cand:
                    continue
                return cand
            return DIR_CYCLE[base]

        # ---------------- dispatch by dominant drive ----------------
        if dominant == "curiosity":
            behavior = "explore"
            # strong push to explore when bored or when explicit pressure high
            if least_visited:
                action = least_visited[0]
                # if boredom is low and explore pressure tiny, occasionally cycle to avoid tight local bias
                if b < 0.25 and ep < 0.2 and self.last_action == action:
                    action = choose_cycle()
            else:
                action = choose_cycle()

        elif dominant == "stability":
            behavior = "settle"
            # prefer most-visited neighbor: reverse of least_visited
            # (i.e., walk where we've been, to reduce variance)
            action = "noop"
            if least_visited:
                most_dirs = list(reversed(list(least_visited)))
                for d in most_dirs:
                    if d in {"up", "down", "left", "right"}:
                        # avoid immediate direction flip-flop
                        if not (self.last_action and OPPOSITE.get(self.last_action) == d):
                            action = d
                            break
                # fallback if the only good option is the opposite of last step
                if action == "noop":
                    for d in most_dirs:
                        if d in {"up", "down", "left", "right"}:
                            action = d
                            break
            # small chance to pause if settle pressure high and we’re still moving
            if sp >= 0.7 and action != "noop":
                action = "noop"

        elif dominant == "pattern_completion":
            behavior = "complete"
            # simple sweep to revisit neighborhood
            self._alt = not self._alt
            # try to avoid immediate backtrack
            pref = "left" if self._alt else "right"
            action = pref if OPPOSITE.get(self.last_action) != pref else "up"

        elif dominant == "truth_seeking":
            behavior = "probe"
            # probe with ping; move a step between pings to vary view
            if self.last_action == "ping":
                # move in cycle, avoiding backtrack
                action = choose_cycle()
            else:
                action = "ping"

        elif dominant == "caregiver_alignment":
            behavior = "align"
            action = "noop"

        elif dominant == "overload_regulation":
            behavior = "cooldown"
            action = "noop"

        else:
            behavior = "default"
            action = "noop"

        self.last_action = action
        return behavior, action
