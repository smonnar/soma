from __future__ import annotations

from typing import Any, Dict, List, Tuple
import math

EMPTY = "."

COLORS = ["R", "G", "B", "Y"]
SHAPES = ["o", "^", "s"]


def _is_token(t: str) -> bool:
    return t not in (EMPTY, "@", " ") and len(t) == 2


def extract_features(obs: Dict[str, Any], *, grid_size: int) -> Dict[str, Any]:
    """Compute simple, normalized features from an observation.

    Returns a dict with scalars in [0,1] where sensible, plus small histograms.
    """
    view: List[List[str]] = obs["view"]
    summary: Dict[str, Any] = obs.get("summary", {})
    agent = obs.get("agent", {"x": 0, "y": 0})

    H = len(view)
    W = len(view[0]) if H else 0
    n_cells = max(1, H * W - 1)  # minus agent cell

    # Token histograms
    counts: Dict[str, int] = summary.get("counts", {})
    uniq: List[str] = list(summary.get("unique", []))
    color_hist = {c: 0 for c in COLORS}
    shape_hist = {s: 0 for s in SHAPES}
    total_tokens = 0
    for tok, c in counts.items():
        if isinstance(tok, str) and len(tok) == 2:
            col, shp = tok[0], tok[1]
            if col in color_hist:
                color_hist[col] += int(c)
            if shp in shape_hist:
                shape_hist[shp] += int(c)
            total_tokens += int(c)

    # Density / diversity
    occupied = sum(1 for row in view for t in row if _is_token(t))
    density = occupied / float(n_cells)
    diversity = (len(uniq) / float(n_cells)) if n_cells else 0.0

    # Entropy over token distribution (normalized by log2 K)
    K = max(1, len(uniq))
    total = sum(counts.values()) or 1
    ent = 0.0
    for tok in uniq:
        p = counts.get(tok, 0) / total
        if p > 0:
            ent -= p * math.log(p, 2)
    entropy = ent / math.log(max(2, K), 2)

    # Directional densities around agent
    cx = H // 2
    cy = W // 2
    up = down = left = right = 0
    upN = downN = leftN = rightN = 0
    for y in range(H):
        for x in range(W):
            if x == cx and y == cy:
                continue
            t = view[y][x]
            if y < cy:
                upN += 1
                if _is_token(t):
                    up += 1
            if y > cy:
                downN += 1
                if _is_token(t):
                    down += 1
            if x < cx:
                leftN += 1
                if _is_token(t):
                    left += 1
            if x > cx:
                rightN += 1
                if _is_token(t):
                    right += 1
    dir_up = up / float(max(1, upN))
    dir_down = down / float(max(1, downN))
    dir_left = left / float(max(1, leftN))
    dir_right = right / float(max(1, rightN))

    # Edge proximity (1 at edge, 0 at center) then invert to proximity_to_center
    x, y = agent.get("x", 0), agent.get("y", 0)
    min_to_edge = min(x, y, grid_size - 1 - x, grid_size - 1 - y)
    max_min = (grid_size - 1) / 2.0
    edge_prox = 1.0 - (min_to_edge / max(1e-6, max_min))  # 0 center → 1 edge
    center_prox = 1.0 - edge_prox

    # Normalize histograms to proportions
    color_prop = {k: (v / total_tokens if total_tokens else 0.0) for k, v in color_hist.items()}
    shape_prop = {k: (v / total_tokens if total_tokens else 0.0) for k, v in shape_hist.items()}

    return {
        "density": float(density),
        "diversity": float(diversity),
        "entropy": float(entropy),
        "center_prox": float(center_prox),
        "dir": {
            "up": float(dir_up),
            "down": float(dir_down),
            "left": float(dir_left),
            "right": float(dir_right),
        },
        "color": color_prop,
        "shape": shape_prop,
        "unique": uniq,
        "counts": counts,
    }