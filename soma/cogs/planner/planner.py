from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

ACTIONS = ["noop", "up", "down", "left", "right", "ping"]
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
DIR_CYCLE = ["up", "right", "down", "left"]


class BehaviorPlanner:
    """Map dominant drive → behavior → action proposal (heuristic v1).

    Behaviors:
      - curiosity → "explore": cycle directions, avoid immediate oscillation
      - stability → "settle": prefer noop; if high change, step back (opposite last move)
      - pattern_completion → "revisit": small local scan (alternating left/right)
      - truth_seeking → "probe": ping; if just pinged, nudge up
      - caregiver_alignment → "align": noop (placeholder)
      - overload_regulation → "cooldown": noop
    """

    def __init__(self):
        self.recent_pos: Deque[Tuple[int, int]] = deque(maxlen=8)
        self.last_action: Optional[str] = None
        self._alt = False  # tiny toggle for alternating patterns

    def propose(
        self,
        *,
        tick: int,
        rng_seed: int,
        dominant: str,
        curiosity: Dict[str, float | List[str]],
        matches: List[Tuple[int, float]],
        pos: Tuple[int, int],
    ) -> Tuple[str, str]:
        self.recent_pos.append(pos)
        novelty = float(curiosity.get("novelty", 0.0))
        change = float(curiosity.get("change", 0.0))

        if dominant == "curiosity":
            behavior = "explore"
            base = (rng_seed + tick) % 4
            for i in range(4):
                cand = DIR_CYCLE[(base + i) % 4]
                if self.last_action and OPPOSITE.get(self.last_action) == cand:
                    continue  # avoid immediate backtrack oscillation
                action = cand
                break
            else:
                action = DIR_CYCLE[base]

        elif dominant == "stability":
            behavior = "settle"
            if change > 0.6 and self.last_action in OPPOSITE:
                action = OPPOSITE[self.last_action]
            else:
                action = "noop"

        elif dominant == "pattern_completion":
            behavior = "revisit"
            # small local scan left/right
            self._alt = not self._alt
            action = "left" if self._alt else "right"

        elif dominant == "truth_seeking":
            behavior = "probe"
            if self.last_action == "ping":
                action = "up"
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