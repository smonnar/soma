from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from soma.cogs.self_notes.notes import SelfNotes


@dataclass
class LearningState:
    ema_novelty: float = 1.0
    prev_coverage: float = 0.0
    curiosity_mod: float = 0.0     # [-0.5, +0.5]
    stability_mod: float = 0.0     # [-0.5, +0.5]
    explore_pressure: float = 0.0  # [0,1]
    settle_pressure: float = 0.0   # [0,1]
    last_reward: float = 0.0


class LearningManager:
    """Tiny adaptive controller for SOMA.

    - Tracks novelty EMA & coverage.
    - Computes a scalar reward from novelty delta, coverage gain, and stall penalty.
    - Applies slow updates to drive gain modifiers and planner exploration/settle pressures.
    """

    def __init__(self, notes: SelfNotes, *, ema_beta: float = 0.2, lr: float = 0.05, decay: float = 0.02) -> None:
        self.notes = notes
        self.beta = float(ema_beta)
        self.lr = float(lr)
        self.decay = float(decay)
        self.s = LearningState()

    # ---------- public API ----------
    def gain_mods(self) -> Dict[str, float]:
        return {
            "curiosity": self.s.curiosity_mod,
            "stability": self.s.stability_mod,
        }

    def planner_bias(self) -> Dict[str, float]:
        return {
            "explore": self.s.explore_pressure,
            "settle": self.s.settle_pressure,
        }

    def update(self, *, tick: int, novelty: float, coverage: float, moved: bool, noop_streak: int, boredom: float) -> Dict[str, Any]:
        # Reward components
        novelty_delta = float(novelty) - self.s.ema_novelty
        coverage_delta = float(coverage) - self.s.prev_coverage
        stall_pen = 1.0 if (noop_streak >= 4) else 0.0

        r = 0.6 * max(0.0, novelty_delta) + 0.3 * max(0.0, coverage_delta) + 0.2 * (1.0 if moved else 0.0) - 0.5 * stall_pen * float(boredom)

        # Decay toward baseline
        self.s.curiosity_mod *= (1.0 - self.decay)
        self.s.stability_mod *= (1.0 - self.decay)
        self.s.explore_pressure *= (1.0 - self.decay)
        self.s.settle_pressure *= (1.0 - self.decay)

        # Apply updates
        self.s.curiosity_mod += self.lr * r
        self.s.stability_mod -= 0.5 * self.lr * r
        if r > 0.0:
            self.s.explore_pressure += self.lr * r
        else:
            # Small push toward exploration when stalled
            self.s.explore_pressure += 0.05 * (1.0 if noop_streak >= 4 else 0.0)
            self.s.settle_pressure += 0.02 * (1.0 if noop_streak == 0 else 0.0)

        # Clamp ranges
        self.s.curiosity_mod = max(-0.5, min(0.5, self.s.curiosity_mod))
        self.s.stability_mod = max(-0.5, min(0.5, self.s.stability_mod))
        self.s.explore_pressure = max(0.0, min(1.0, self.s.explore_pressure))
        self.s.settle_pressure = max(0.0, min(1.0, self.s.settle_pressure))

        # Update trackers
        self.s.ema_novelty = (1.0 - self.beta) * self.s.ema_novelty + self.beta * float(novelty)
        self.s.prev_coverage = float(coverage)
        self.s.last_reward = float(r)

        # Note significant changes
        if abs(r) >= 0.25 or (tick % 20 == 0):
            self.notes.note(
                kind="learning",
                payload={
                    "tick": tick,
                    "reward": round(self.s.last_reward, 3),
                    "mods": {"curiosity": round(self.s.curiosity_mod, 3), "stability": round(self.s.stability_mod, 3)},
                    "bias": {"explore": round(self.s.explore_pressure, 3), "settle": round(self.s.settle_pressure, 3)},
                    "novelty_ema": round(self.s.ema_novelty, 3),
                    "coverage": round(self.s.prev_coverage, 3),
                },
                tick=tick,
            )

        return {
            "reward": self.s.last_reward,
            "mods": self.gain_mods(),
            "bias": self.planner_bias(),
        }