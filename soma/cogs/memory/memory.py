from __future__ import annotations

from math import sqrt
from typing import Dict, List, Optional, Tuple

from .assoc import AssocGraph


def _cos(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    s = 0.0
    na = 0.0
    nb = 0.0
    # assume equal dims; guard length mismatch
    m = min(len(a), len(b))
    for i in range(m):
        va = float(a[i])
        vb = float(b[i])
        s += va * vb
        na += va * va
        nb += vb * vb
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(s) / float(sqrt(na) * sqrt(nb))


class MemorySystem:
    """
    Minimal vector store with cosine similarity + lightweight co-occurrence graph.

    Public API used elsewhere:
      - add_vector(tick, vector, meta)
      - query(vector, top_k, min_score)
      - assoc: AssocGraph (for optional downstream use)
    """

    def __init__(self, dim: int, max_items: int = 1024) -> None:
        self.dim = int(dim)
        self.max_items = int(max_items)
        self.vecs: List[List[float]] = []
        self.ticks: List[int] = []
        self.meta: List[Dict] = []
        self.assoc = AssocGraph()

    # ----------------
    def add_vector(self, *, tick: int, vector: List[float], meta: Optional[Dict] = None) -> None:
        if not isinstance(vector, list):
            # attempt to coerce numpy arrays etc.
            try:
                vector = [float(x) for x in vector]
            except Exception:
                return
        if self.dim and len(vector) != self.dim:
            # soft guard; truncate/pad
            if len(vector) > self.dim:
                vector = vector[: self.dim]
            else:
                vector = vector + [0.0] * (self.dim - len(vector))
        self.vecs.append(vector)
        self.ticks.append(int(tick))
        m = dict(meta or {})
        self.meta.append(m)

        # --- update co-occurrence graph if features are present ---
        feats = m.get("features", {}) if isinstance(m, dict) else {}
        # expect token lists under common keys
        toks = []
        for key in ("unique", "colors", "shapes", "tokens"):
            v = feats.get(key)
            if isinstance(v, list):
                toks.extend([str(x) for x in v])
        if toks:
            self.assoc.add_event(toks)

        # capacity control
        if len(self.vecs) > self.max_items:
            self.vecs.pop(0)
            self.ticks.pop(0)
            self.meta.pop(0)

    # ----------------
    def query(self, vector: List[float], *, top_k: int = 3, min_score: float = 0.5) -> List[Tuple[int, float]]:
        if not self.vecs:
            return []
        sims: List[Tuple[int, float]] = []  # (tick, score)
        for stored, t in zip(self.vecs, self.ticks):
            s = _cos(vector, stored)
            if s >= float(min_score):
                sims.append((t, float(s)))
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[: int(top_k)]