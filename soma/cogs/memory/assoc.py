from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass
class AssocStats:
    token: str
    assoc: List[Tuple[str, int]]  # [(other, count), ...]


class AssocGraph:
    """
    Tiny co-occurrence graph for tokens seen together in the *same tick*.

    - Undirected counts (A,B) == (B,A)
    - No external deps (no networkx) for portability
    - Enough to support pattern-completion and simple neighborhood queries
    """

    def __init__(self) -> None:
        self._adj: Dict[str, Counter] = defaultdict(Counter)

    # ----------------
    def add_event(self, tokens: Iterable[str]) -> None:
        toks = [t for t in (tokens or []) if isinstance(t, str) and t]
        n = len(toks)
        if n < 2:
            return
        # undirected pair counts
        for i in range(n):
            a = toks[i]
            for j in range(i + 1, n):
                b = toks[j]
                if a == b:
                    continue
                self._adj[a][b] += 1
                self._adj[b][a] += 1

    def add_pair(self, a: str, b: str, w: int = 1) -> None:
        if not a or not b or a == b:
            return
        self._adj[a][b] += int(w)
        self._adj[b][a] += int(w)

    # ----------------
    def neighbors(self, token: str, min_count: int = 1) -> List[Tuple[str, int]]:
        c = self._adj.get(token, Counter())
        return [(k, v) for k, v in c.most_common() if v >= min_count]

    def top_assoc(self, token: str, k: int = 5) -> List[Tuple[str, int]]:
        return self.neighbors(token)[:k]

    def stats(self) -> List[AssocStats]:
        out: List[AssocStats] = []
        for t, cnt in self._adj.items():
            out.append(AssocStats(token=t, assoc=cnt.most_common()))
        return out

    # ---------------- serialization ----------------
    def to_json(self) -> Dict[str, Dict[str, int]]:
        return {a: dict(c) for a, c in self._adj.items()}

    @classmethod
    def from_json(cls, obj: Dict[str, Dict[str, int]]) -> "AssocGraph":
        g = cls()
        for a, d in (obj or {}).items():
            for b, w in (d or {}).items():
                g.add_pair(a, b, int(w))
        return g