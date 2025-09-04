from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Tuple
import hashlib
import math


@dataclass
class MemoryItem:
    tick: int
    vector: List[float]  # L2-normalized
    meta: Dict[str, object]


class MemorySystem:
    def __init__(self, dim: int = 64, max_items: int = 512):
        self.dim = dim
        self.buf: Deque[MemoryItem] = deque(maxlen=max_items)

    def _hash_idx(self, token: str) -> int:
        h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(h, "little") % self.dim

    def embed(self, summary: Dict[str, object]) -> List[float]:
        counts: Dict[str, int] = summary.get("counts", {})  # type: ignore
        vec = [0.0] * self.dim
        for token, c in counts.items():
            i = self._hash_idx(str(token))
            vec[i] += float(c)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def add(self, tick: int, summary: Dict[str, object], action: str | None) -> None:
        vec = self.embed(summary)
        meta = {"unique": summary.get("unique", []), "counts": summary.get("counts", {}), "action": action}
        self.buf.append(MemoryItem(tick=tick, vector=vec, meta=meta))

    def add_vector(self, tick: int, vector: List[float], meta: Dict[str, object]) -> None:
        # Ensure length and normalization
        v = list(vector)
        if len(v) != self.dim:
            # pad/trim to fit
            if len(v) < self.dim:
                v = v + [0.0] * (self.dim - len(v))
            else:
                v = v[: self.dim]
        n = math.sqrt(sum(x * x for x in v))
        if n > 0:
            v = [x / n for x in v]
        self.buf.append(MemoryItem(tick=tick, vector=v, meta=meta))

    def query(self, vec: List[float], top_k: int = 3, min_score: float = 0.35) -> List[Tuple[int, float]]:
        def dot(a: List[float], b: List[float]) -> float:
            return sum(x * y for x, y in zip(a, b))
        scored: List[Tuple[int, float]] = []
        for item in self.buf:
            s = dot(vec, item.vector)
            s = max(0.0, min(1.0, s))
            if s >= min_score:
                scored.append((item.tick, float(s)))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]