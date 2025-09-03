from __future__ import annotations
from typing import Any
from .gridworld import GridWorldV0, ACTIONS

def make_env(name: str, **kwargs: Any):
    name = name.lower()
    if name in {"grid", "grid-v0", "gridworld-v0"}:
        return GridWorldV0(**kwargs)
    raise ValueError(f"Unknown env name: {name}")

__all__ = ["make_env", "ACTIONS", "GridWorldV0"]