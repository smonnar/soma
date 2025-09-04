from __future__ import annotations

from typing import Any, Dict, List, Tuple
import math

from soma.cogs.memory.memory import MemorySystem
from soma.cogs.self_notes.notes import SelfNotes


class CuriosityEngine:
    """Compute curiosity signals from the current summary and memory.

    Outputs:
      - novelty: 1 - max cosine similarity to memory (0..1)
      - change: Jaccard distance vs. previous unique tokens (0..1)
      - rarity: mean normalized IDF over tokens in view (0..1)
      - attention: up to K tokens to focus on (new and/or rare)
    """

    def __init__(self, notes: SelfNotes, novelty_threshold: float = 0.6, change_threshold: float = 0.5, top_k: int = 3):
        self.notes = notes
        self.novelty_threshold = float(novelty_threshold)
        self.change_threshold = float(change_threshold)
        self.top_k = int(top_k)
        self._prev_unique: List[str] = []

    # ------------------------- helpers -------------------------
    def _doc_freqs(self, memory: MemorySystem) -> Dict[str, int]:
        df: Dict[str, int] = {}
        for item in memory.buf:
            counts = item.meta.get("counts", {})
            if isinstance(counts, dict):
                for t in counts.keys():
                    df[t] = df.get(t, 0) + 1
        return df

    def _idf_norm(self, df: Dict[str, int], N: int, token: str) -> float:
        if N <= 0:
            return 1.0
        # normalized IDF in [0,1]
        return math.log((N + 1) / (df.get(token, 0) + 1)) / math.log(N + 1)

    # --------------------------- API ---------------------------
    def assess(
        self,
        *,
        tick: int,
        summary: Dict[str, Any],
        matches: List[Tuple[int, float]],
        memory: MemorySystem,
    ) -> Dict[str, float | List[str]]:
        uniq: List[str] = list(summary.get("unique", []))

        # novelty from recall matches (cosine similarity)
        max_sim = float(matches[0][1]) if matches else 0.0
        max_sim = max(0.0, min(1.0, max_sim))
        novelty = 1.0 - max_sim

        # change via Jaccard distance vs previous unique set
        a, b = set(self._prev_unique), set(uniq)
        change = 0.0
        if a or b:
            change = 1.0 - (len(a & b) / float(len(a | b)))

        # rarity via normalized IDF over tokens in view
        df = self._doc_freqs(memory)
        N = len(memory.buf)
        if uniq:
            rarity_vals = [self._idf_norm(df, N, t) for t in uniq]
            rarity = float(sum(rarity_vals) / len(rarity_vals))
        else:
            rarity = 0.0

        # attention: prioritize new tokens, then rare ones
        new_tokens = [t for t in uniq if t not in self._prev_unique]
        rare_sorted = sorted(uniq, key=lambda t: df.get(t, 0))
        seen = set()
        attention: List[str] = []
        for t in new_tokens + rare_sorted:
            if t not in seen:
                seen.add(t)
                attention.append(t)
            if len(attention) >= self.top_k:
                break

        # note if thresholds crossed
        if novelty >= self.novelty_threshold or change >= self.change_threshold:
            self.notes.note(
                kind="curiosity",
                payload={
                    "tick": tick,
                    "novelty": round(novelty, 3),
                    "change": round(change, 3),
                    "rarity": round(rarity, 3),
                    "attention": attention,
                    "top_match": matches[0] if matches else None,
                },
                tick=tick,
            )

        # update previous
        self._prev_unique = uniq

        return {
            "novelty": novelty,
            "change": change,
            "rarity": rarity,
            "attention": attention,
        }