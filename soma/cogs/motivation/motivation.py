from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from soma.cogs.self_notes.notes import SelfNotes


DriveName = str


@dataclass
class DriveParams:
    decay: float  # leak per tick (0..1); higher = faster decay
    gain: float   # scale stimulus → increment
    setpoint: float = 0.0  # homeostatic target (used by some drives)


class MotivationManager:
    """Simple multi-drive homeostat with leaky integrators.

    Drives (v1):
      - curiosity: energized by novelty/rarity/change
      - stability: energized by similarity/low-change (+ a bit on overload)
      - pattern_completion: energized by mid-similarity recalls
      - truth_seeking: energized by high novelty + high change
      - caregiver_alignment: mild pull toward a baseline (for future interface)
      - overload_regulation: spikes when reflex overload triggers

    Values are clamped to [0, 1].
    """

    def __init__(self, notes: SelfNotes):
        self.notes = notes
        self.params: Dict[DriveName, DriveParams] = {
            "curiosity": DriveParams(decay=0.08, gain=0.9),
            "stability": DriveParams(decay=0.06, gain=0.8),
            "pattern_completion": DriveParams(decay=0.07, gain=0.7),
            "truth_seeking": DriveParams(decay=0.09, gain=0.9),
            "caregiver_alignment": DriveParams(decay=0.03, gain=0.2, setpoint=0.2),
            "overload_regulation": DriveParams(decay=0.20, gain=1.0),
        }
        self.state: Dict[DriveName, float] = {k: (p.setpoint if p.setpoint > 0 else 0.0) for k, p in self.params.items()}
        self._last_dominant: Optional[DriveName] = None

    @staticmethod
    def _clamp(x: float) -> float:
        return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

    def _apply(self, name: DriveName, stimulus: float) -> None:
        p = self.params[name]
        v = self.state[name]
        # Leak toward 0, then add stimulus scaled by gain; bias toward setpoint if present
        leaked = (1.0 - p.decay) * v
        toward_set = p.setpoint * p.decay  # tiny pull to baseline per tick
        v_next = leaked + p.gain * max(0.0, stimulus) + toward_set
        self.state[name] = self._clamp(v_next)

    def update(
        self,
        *,
        tick: int,
        curiosity: Dict[str, float | List[str]],  # from CuriosityEngine.assess
        matches: List[Tuple[int, float]],         # (tick, cosine)
        reflex_triggers: List[str],
    ) -> Dict[DriveName, float]:
        nov = float(curiosity.get("novelty", 0.0))
        chg = float(curiosity.get("change", 0.0))
        rar = float(curiosity.get("rarity", 0.0))
        max_sim = float(matches[0][1]) if matches else 0.0
        mid_sim = 1.0 if 0.3 <= max_sim <= 0.8 else 0.0
        overloaded = 1.0 if ("overload" in reflex_triggers) else 0.0

        # Stimuli heuristics (bounded in [0,1])
        stim_curiosity = min(1.0, 0.6 * nov + 0.2 * rar + 0.2 * chg)
        stim_stability = min(1.0, 0.7 * max_sim + 0.3 * (1.0 - chg) + 0.2 * overloaded)
        stim_pattern = min(1.0, 0.8 * mid_sim + 0.2 * (1.0 - nov))
        stim_truth = min(1.0, 0.5 * nov + 0.5 * chg)
        # caregiver_alignment is biased by setpoint; tiny nudge from novelty to seek labeling when surprised
        stim_caregiver = min(1.0, 0.1 * nov)
        stim_overload = overloaded

        self._apply("curiosity", stim_curiosity)
        self._apply("stability", stim_stability)
        self._apply("pattern_completion", stim_pattern)
        self._apply("truth_seeking", stim_truth)
        self._apply("caregiver_alignment", stim_caregiver)
        self._apply("overload_regulation", stim_overload)

        dominant = max(self.state.items(), key=lambda kv: kv[1])[0]
        if dominant != self._last_dominant:
            self.notes.note(
                kind="motivation",
                payload={
                    "tick": tick,
                    "dominant": dominant,
                    "drives": {k: round(v, 3) for k, v in self.state.items()},
                },
                tick=tick,
            )
            self._last_dominant = dominant

        return self.state

    def dominant(self) -> DriveName:
        return max(self.state.items(), key=lambda kv: kv[1])[0]