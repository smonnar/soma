from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

ACTIONS = ["noop", "up", "down", "left", "right", "ping"]
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
DIR_CYCLE = ["up", "right", "down", "left"]


class BehaviorPlanner:
    """Drive → behavior → action with exploration bias and boredom escape."""

    def __init__(self):
        self.recent_pos: Deque[Tuple[int, int]] = deque(maxlen=8)
        self.last_action: Optional[str] = None
        self._alt = False

    def propose(
        self,
        *,
        tick: int,
        rng_seed: int,
        dominant: str,
        curiosity: Dict[str, float | List[str]],
        matches: List[Tuple[int, float]],
        pos: Tuple[int, int],
        least_visited: List[str],
        boredom: float,
        explore_pressure: float = 0.0,
        settle_pressure: float = 0.0,
    ) -> Tuple[str, str]:
        self.recent_pos.append(pos)
        b = float(boredom)
        ep = float(explore_pressure)
        sp = float(settle_pressure)

        def choose_cycle() -> str:
            base = (rng_seed + tick) % 4
            for i in range(4):
                cand = DIR_CYCLE[(base + i) % 4]
                if self.last_action and OPPOSITE.get(self.last_action) == cand:
                    continue
                return cand
            return DIR_CYCLE[base]

        if dominant == "curiosity":
            behavior = "explore"
            if least_visited:
                action = least_visited[0]
            else:
                action = choose_cycle() if ep < 0.7 else ("up" if (self.last_action != "up") else choose_cycle())

        elif dominant == "stability":
            behavior = "settle"
            if b >= 0.5 and least_visited:
                action = least_visited[0]
            elif sp >= 0.6:
                action = "noop"
            elif self.last_action in OPPOSITE and b > 0.3:
                action = OPPOSITE[self.last_action]
            else:
                action = "noop"

        elif dominant == "pattern_completion":
            behavior = "revisit"
            self._alt = not self._alt
            action = "left" if self._alt else "right"

        elif dominant == "truth_seeking":
            behavior = "probe"
            action = "up" if self.last_action == "ping" else "ping"

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