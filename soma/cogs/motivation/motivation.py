from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from soma.cogs.self_notes.notes import SelfNotes


DriveName = str


@dataclass
class DriveParams:
    decay: float
    gain: float
    setpoint: float = 0.0


class MotivationManager:
    """Multi-drive homeostat with boredom coupling and optional gain modifiers."""

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

    def _apply(self, name: DriveName, stimulus: float, gain_mod: float = 0.0) -> None:
        p = self.params[name]
        v = self.state[name]
        leaked = (1.0 - p.decay) * v
        toward_set = p.setpoint * p.decay
        # apply gain modifier (1 + mod) multiplicative
        eff = max(0.0, stimulus) * max(0.0, 1.0 + float(gain_mod))
        v_next = leaked + p.gain * eff + toward_set
        self.state[name] = self._clamp(v_next)

    def update(
        self,
        *,
        tick: int,
        curiosity: Dict[str, float | List[str]],
        matches: List[Tuple[int, float]],
        reflex_triggers: List[str],
        boredom: float = 0.0,
        gain_mods: Dict[DriveName, float] | None = None,
    ) -> Dict[DriveName, float]:
        gain_mods = gain_mods or {}
        nov = float(curiosity.get("novelty", 0.0))
        chg = float(curiosity.get("change", 0.0))
        rar = float(curiosity.get("rarity", 0.0))
        max_sim = float(matches[0][1]) if matches else 0.0
        mid_sim = 1.0 if 0.3 <= max_sim <= 0.8 else 0.0
        overloaded = 1.0 if ("overload" in reflex_triggers) else 0.0

        b = max(0.0, min(1.0, boredom))

        stim_curiosity = min(1.0, 0.5 * nov + 0.2 * rar + 0.3 * chg + 0.3 * b)
        stim_stability = min(1.0, max(0.0, 0.7 * max_sim + 0.3 * (1.0 - chg) - 0.4 * b) + 0.2 * overloaded)
        stim_pattern = min(1.0, 0.8 * mid_sim + 0.2 * (1.0 - nov))
        stim_truth = min(1.0, 0.5 * nov + 0.5 * chg)
        stim_caregiver = min(1.0, 0.1 * nov)
        stim_overload = overloaded

        self._apply("curiosity", stim_curiosity, gain_mods.get("curiosity", 0.0))
        self._apply("stability", stim_stability, gain_mods.get("stability", 0.0))
        self._apply("pattern_completion", stim_pattern, gain_mods.get("pattern_completion", 0.0))
        self._apply("truth_seeking", stim_truth, gain_mods.get("truth_seeking", 0.0))
        self._apply("caregiver_alignment", stim_caregiver, gain_mods.get("caregiver_alignment", 0.0))
        self._apply("overload_regulation", stim_overload, gain_mods.get("overload_regulation", 0.0))

        dominant = max(self.state.items(), key=lambda kv: kv[1])[0]
        if dominant != self._last_dominant:
            self.notes.note(
                kind="motivation",
                payload={
                    "tick": tick,
                    "dominant": dominant,
                    "boredom": round(b, 3),
                    "drives": {k: round(v, 3) for k, v in self.state.items()},
                },
                tick=tick,
            )
            self._last_dominant = dominant

        return self.state