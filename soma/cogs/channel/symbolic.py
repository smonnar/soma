from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

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


@dataclass
class _ChannelState:
    cooldown: int = 0
    prev_boredom: float = 0.0
    prev_novelty: float = 0.0


class SymbolicChannel:
    """
    Emits compact symbols about the agent's state with mild rate-limiting.
    """

    def __init__(
        self,
        notes: SelfNotes,
        *,
        novelty_hi: float = 0.80,
        novelty_up: float = 0.20,
        boredom_hi: float = 0.65,
        recall_hi: float = 0.65,
        loop_noop: int = 5,
        cooldown_ticks: int = 3,  # widened from 1 to reduce spam
    ) -> None:
        self.notes = notes
        self.novelty_hi = float(novelty_hi)
        self.novelty_up = float(novelty_up)
        self.boredom_hi = float(boredom_hi)
        self.recall_hi = float(recall_hi)
        self.loop_noop = int(loop_noop)
        self.cooldown_ticks = int(cooldown_ticks)

        self.ext_tags: Dict[str, str] = {}
        self.s = _ChannelState()

    # external caregiver tags for tokens
    def set_tags(self, tags: Dict[str, str]) -> None:
        self.ext_tags = dict(tags or {})

    # helpers
    @staticmethod
    def encode(tokens: List[str]) -> str:
        return " ".join(tokens)

    @staticmethod
    def decode(s: str) -> List[str]:
        return [t for t in s.split() if t in VOCAB]

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
    ) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
        """
        Decide whether to emit symbols for this tick.
        Returns (tokens, glosses, caregiver_pairs).
        """
        tokens: List[str] = []
        gloss: List[str] = []
        ext_pairs: List[Tuple[str, str]] = []

        # ----- rule: overload reflex
        if any(t.lower().startswith("over") for t in reflex_triggers or []):
            tokens.append("Over!")

        # ----- rule: novelty spikes / rising novelty
        if novelty >= self.novelty_hi:
            tokens.append("N!")
        elif novelty - self.s.prev_novelty >= self.novelty_up and novelty >= 0.4:
            tokens.append("N↑")

        # ----- rule: boredom (stability down) — emit on threshold crossing or rising boredom
        emit_stab = (boredom >= self.boredom_hi) and (
            boredom > self.s.prev_boredom or self.s.prev_boredom < self.boredom_hi
        )
        if emit_stab:
            tokens.append("Stab↓")

        # ----- rule: contradiction / mismatch heuristic
        # If memory says "this looks familiar" but novelty is still elevated, flag "?"
        top_sim = matches[0][1] if matches else 0.0
        if top_sim >= self.recall_hi and novelty >= 0.5:
            tokens.append("?")

        # ----- optional: pattern completion drive marker
        if dominant == "pattern_completion":
            tokens.append("Pat→")

        # ----- rate limiting via cooldown
        if tokens and self.s.cooldown == 0:
            self.s.cooldown = self.cooldown_ticks
            gloss = [VOCAB[t] for t in tokens if t in VOCAB]
            # caregiver gloss pairs
            for t in tokens:
                if t in self.ext_tags:
                    ext_pairs.append((t, self.ext_tags[t]))
            # structured note
            self.notes.note(
                kind="symbol",
                payload={
                    "tick": tick,
                    "emit": tokens,
                    "gloss": gloss,
                    "caregiver_gloss": ext_pairs,
                    "novelty": round(float(novelty), 3),
                    "boredom": round(float(boredom), 3),
                    "top_sim": round(float(top_sim), 3),
                },
                tick=tick,
            )
        else:
            # suppress this tick (cooldown active or no tokens)
            tokens, gloss, ext_pairs = [], [], []

        # ----- update internal state for next tick
        self.s.prev_boredom = float(boredom)
        self.s.prev_novelty = float(novelty)
        if self.s.cooldown > 0:
            self.s.cooldown -= 1

        return tokens, gloss, ext_pairs
