from __future__ import annotations

from collections import deque
from typing import Deque, List, Tuple

from soma.cogs.self_notes.notes import SelfNotes
from soma.sandbox.gridworld import ACTIONS


OSCILLATION_PAIRS = {("left", "right"), ("up", "down")}


def _is_two_way_oscillation(seq: List[str]) -> bool:
    if len(seq) < 4:
        return False
    a, b = seq[-2], seq[-1]
    if (a, b) not in OSCILLATION_PAIRS and (b, a) not in OSCILLATION_PAIRS:
        return False
    # Check last 4 form A,B,A,B pattern
    return len(seq) >= 4 and seq[-4] == a and seq[-3] == b and seq[-2] == a and seq[-1] == b


class ReflexManager:
    """Detect simple instability patterns and suggest safe overrides.

    Policies (v1):
      - overload: if too many unique tokens in the 3x3 view, prefer noop to stabilize.
      - loop_break: if we detect A,B,A,B oscillation (left/right or up/down), break with a ping.
      - edge_guard: if an unknown action shows up, force noop.
    Every trigger emits a self-note with details.
    """

    def __init__(
        self,
        notes: SelfNotes,
        overload_unique_threshold: int = 4,
        history: int = 8,
    ) -> None:
        self.notes = notes
        self.overload_unique_threshold = overload_unique_threshold
        self.last_actions: Deque[str] = deque(maxlen=history)

    def advise(self, tick: int, selected: str, unique_tokens: List[str]) -> Tuple[str, List[str]]:
        triggers: List[str] = []
        action = selected

        # Edge guard first
        if action not in ACTIONS:
            triggers.append("edge_guard")
            action = "noop"

        # Overload: too many distinct items in immediate view
        if len(unique_tokens) >= self.overload_unique_threshold:
            triggers.append("overload")
            action = "noop"

        # Loop-break: A,B,A,B oscillation
        recent = list(self.last_actions)
        recent.append(action)
        if _is_two_way_oscillation(recent):
            triggers.append("loop_break")
            action = "ping"

        # Log self-note if any trigger fired
        if triggers:
            self.notes.note(
                kind="reflex",
                payload={
                    "tick": tick,
                    "triggers": triggers,
                    "original": selected,
                    "override": action,
                    "unique": unique_tokens,
                },
                tick=tick,
            )

        # Update history with the *final* action we will execute
        self.last_actions.append(action)
        return action, triggers