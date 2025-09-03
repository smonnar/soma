from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict


class StateSnapshot(BaseModel):
    """Minimal, serializable state for a single tick.

    This will grow in later milestones to include drive levels, memory refs, etc.
    """

    tick: int = 0
    rng_seed: int = 0
    info: Dict[str, Any] = Field(default_factory=dict)

    def next(self) -> "StateSnapshot":
        """Advance to the next tick with a simple LCG seed update.

        We intentionally avoid importing `random` for full determinism
        from the seed and to keep the state self-contained.
        """
        next_seed = (self.rng_seed * 1664525 + 1013904223) % (2**32)
        return StateSnapshot(tick=self.tick + 1, rng_seed=next_seed, info={})