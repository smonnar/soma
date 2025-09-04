from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

from soma.cogs.self_notes.notes import SelfNotes


VOCAB: Dict[str, str] = {
    "N!": "sharp novelty (surprise)",
    "N↑": "novelty rising",
    "Stab↓": "stability declining / restless",
    "?": "possible contradiction / mismatch",
    "Over!": "sensory overload",
    "Loop?": "repetition / loop risk",
    "Pat→": "pattern completion drive active",
}


def _unique_key(summary: Dict[str, Any]) -> Tuple[str, ...]:
    # Stable signature of the current view's unique tokens
    uniq = summary.get("unique", []) or []
    return tuple(sorted(str(u) for u in uniq))


@dataclass
class ChannelState:
    last_novelty: float = 1.0
    last_unique: Tuple[str, ...] | None = None
    cooldown: int = 0


class SymbolicChannel:
    """Minimal symbolic externalization with a tiny vocabulary and conservative policy.

    Policy highlights:
      - Emit **N!** when novelty is very high.
      - Emit **N↑** on a significant novelty uptick.
      - Emit **Over!** when reflex indicates overload.
      - Emit **Loop?** when noop_streak exceeds a threshold.
      - Emit **?** when novelty is high *and* top recall similarity is also high (familiar-but-different).
      - Emit **Stab↓** when boredom is high while Stability is not dominant.
      - Emit **Pat→** when Pattern Completion dominates (placeholder until richer M12 puzzles).

    Emissions are written as self-notes: kind="symbol".
    """

    def __init__(self, notes: SelfNotes, *, novelty_hi: float = 0.85, novelty_up: float = 0.25, boredom_hi: float = 0.7, recall_hi: float = 0.7, loop_noop: int = 6, cooldown_ticks: int = 2) -> None:
        self.notes = notes
        self.s = ChannelState()
        self.novelty_hi = float(novelty_hi)
        self.novelty_up = float(novelty_up)
        self.boredom_hi = float(boredom_hi)
        self.recall_hi = float(recall_hi)
        self.loop_noop = int(loop_noop)
        self.cooldown_ticks = int(cooldown_ticks)

    # -------- encoder/decoder (toy) --------
    @staticmethod
    def encode(tokens: List[str]) -> str:
        return " ".join(tokens)

    @staticmethod
    def decode(s: str) -> List[str]:
        return [t for t in s.split() if t in VOCAB]

    # -------- core policy --------
    def maybe_emit(
        self,
        *,
        tick: int,
        novelty: float,
        boredom: float,
        matches: List[Tuple[int, float]],
        summary: Dict[str, Any],
        drives: Dict[str, float],
        dominant: str,
        noop_streak: int,
        reflex_triggers: List[str],
    ) -> Tuple[List[str], List[str]]:
        tokens: List[str] = []
        gloss: List[str] = []

        # Cooldown to avoid spam
        if self.s.cooldown > 0:
            self.s.cooldown -= 1
        
        # Compute simple conditions
        top_sim = float(matches[0][1]) if matches else 0.0
        uniq_key = _unique_key(summary)
        last_n = float(self.s.last_novelty)
        dn = novelty - last_n

        # Rules
        if novelty >= self.novelty_hi:
            tokens.append("N!")
        elif dn >= self.novelty_up and novelty >= 0.4:
            tokens.append("N↑")

        if "overload" in reflex_triggers:
            tokens.append("Over!")

        if noop_streak >= self.loop_noop:
            tokens.append("Loop?")

        # familiar but different → contradiction-ish
        if novelty >= 0.5 and top_sim >= self.recall_hi:
            # If the set of unique tokens changed from last observation, flag a mismatch
            if self.s.last_unique is not None and uniq_key != self.s.last_unique:
                tokens.append("?")

        # Stability down when bored and not stability-dominant
        if boredom >= self.boredom_hi and dominant != "stability":
            tokens.append("Stab↓")

        if dominant == "pattern_completion":
            tokens.append("Pat→")

        # Deduplicate and apply cooldown
        if tokens and self.s.cooldown == 0:
            self.s.cooldown = self.cooldown_ticks
            gloss = [VOCAB[t] for t in tokens if t in VOCAB]
            # Write a self-note
            self.notes.note(
                kind="symbol",
                payload={
                    "tick": tick,
                    "emit": tokens,
                    "gloss": gloss,
                    "novelty": round(float(novelty), 3),
                    "boredom": round(float(boredom), 3),
                    "top_sim": round(float(top_sim), 3),
                },
                tick=tick,
            )
        else:
            tokens = []
            gloss = []

        # Update memory
        self.s.last_novelty = float(novelty)
        self.s.last_unique = uniq_key
        return tokens, gloss

    def vocab(self) -> Dict[str, str]:
        return dict(VOCAB)