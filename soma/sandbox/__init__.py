from __future__ import annotations
from typing import Any

# v0 (your existing module name is gridworld.py)
from .gridworld import GridWorldV0, ACTIONS as V0_ACTIONS
# v1.5 (new)
from .v1 import GridWorldV1

# unify/forward the action set
ACTIONS = list(V0_ACTIONS)

def make_env(name: str, *, size: int, n_objects: int, view_radius: int) -> Any:
    name = (name or "").lower().strip()
    if name in {"grid", "grid-v0", "v0", "gridworld-v0"}:
        return GridWorldV0(size=size, n_objects=n_objects, view_radius=view_radius)
    if name in {"grid-v1", "v1", "grid-v1.5"}:
        return GridWorldV1(size=size, n_objects=n_objects, view_radius=view_radius)
    raise ValueError(f"Unknown env name: {name}")

__all__ = ["make_env", "ACTIONS", "GridWorldV0", "GridWorldV1"]