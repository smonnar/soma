from __future__ import annotations

from typing import List, Tuple

from soma.cogs.self_notes.notes import SelfNotes


class ReflexManager:
    """Reflexes with overload throttle and boredom-based relaxation."""

    def __init__(
        self,
        *,
        notes: SelfNotes,
        overload_unique_threshold: int = 4,
        max_noop_on_overload: int = 3,
        relax_boredom: float = 0.7,
    ) -> None:
        self.notes = notes
        self.overload_unique_threshold = int(overload_unique_threshold)
        self.max_noop_on_overload = int(max_noop_on_overload)
        self.relax_boredom = float(relax_boredom)
        self._overload_streak = 0
        self._last_tick = -1

    def advise(
        self,
        *,
        tick: int,
        selected: str,
        unique_tokens: List[str],
        boredom: float = 0.0,
    ) -> Tuple[str, List[str]]:
        if tick != self._last_tick + 1:
            self._overload_streak = 0
        self._last_tick = tick

        triggers: List[str] = []
        overloaded = len(unique_tokens) >= self.overload_unique_threshold

        if overloaded:
            triggers.append("overload")
            should_relax = (self._overload_streak >= self.max_noop_on_overload) or (boredom >= self.relax_boredom)
            if should_relax:
                triggers.append("relaxed")
                final = selected
                self._overload_streak = max(0, self._overload_streak - 1)
            else:
                final = "noop"
                self._overload_streak += 1
        else:
            final = selected
            self._overload_streak = 0

        if triggers and (final == "noop" or "relaxed" in triggers):
            self.notes.note(
                kind="reflex",
                payload={
                    "tick": tick,
                    "original": selected,
                    "override": final,
                    "triggers": triggers,
                    "overload_streak": self._overload_streak,
                    "boredom": round(float(boredom), 3),
                },
                tick=tick,
            )

        return final, triggers