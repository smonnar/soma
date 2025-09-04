from __future__ import annotations

from typing import Any, Dict, List
import hashlib
import math

COLORS = ["R", "G", "B", "Y"]
SHAPES = ["o", "^", "s"]


class PerceptionEmbedderV2:
    """Blend compact features with a hashed bag of tokens into a 64-dim vector.

    Strategy: start from a hashed 64-dim bag-of-tokens (like MemorySystem.embed), then
    add ~15 feature scalars into the first slots; L2-normalize.
    """

    def __init__(self, dim: int = 64):
        self.dim = dim

    def _hash_idx(self, token: str) -> int:
        h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(h, "little") % self.dim

    def _vec_from_counts(self, counts: Dict[str, int]) -> List[float]:
        v = [0.0] * self.dim
        for tok, c in counts.items():
            i = self._hash_idx(str(tok))
            v[i] += float(c)
        return v

    def _l2(self, v: List[float]) -> List[float]:
        n = math.sqrt(sum(x * x for x in v))
        if n > 0:
            return [x / n for x in v]
        return v

    def embed(self, features: Dict[str, Any]) -> List[float]:
        counts: Dict[str, int] = features.get("counts", {})
        vec = self._vec_from_counts(counts)

        # Build compact feature list (≈15 dims) in [0,1]
        f: List[float] = []
        f.append(float(features.get("density", 0.0)))
        f.append(float(features.get("diversity", 0.0)))
        f.append(float(features.get("entropy", 0.0)))
        f.append(float(features.get("center_prox", 0.0)))
        d = features.get("dir", {})
        f.extend([float(d.get("up", 0.0)), float(d.get("down", 0.0)), float(d.get("left", 0.0)), float(d.get("right", 0.0))])
        c = features.get("color", {})
        f.extend([float(c.get(k, 0.0)) for k in COLORS])
        s = features.get("shape", {})
        f.extend([float(s.get(k, 0.0)) for k in SHAPES])

        # Gently scale features so they don't swamp counts (alpha ~ 0.8)
        alpha = 0.8
        for i, val in enumerate(f):
            if i >= self.dim:
                break
            vec[i] += alpha * val

        return self._l2(vec)