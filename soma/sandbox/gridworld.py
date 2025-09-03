from __future__ import annotations

from typing import Dict, List, Tuple, Any
import random

# Simple symbolic palette (kept tiny on purpose)
COLORS = ["R", "G", "B", "Y"]  # red, green, blue, yellow
SHAPES = ["o", "^", "s"]        # circle, triangle, square

# Public action list (deterministic choice via LCG seed in the core loop)
ACTIONS: List[str] = ["noop", "up", "down", "left", "right", "ping"]

EMPTY = "."


class GridWorldV0:
    """A tiny 2D world with colored shapes. No rewards; just structure to perceive.

    - Grid stores tokens like "Ro" (red circle), "G^" (green triangle), or "." for empty.
    - The agent has a position. Observation is a (2r+1)x(2r+1) viewport around the agent.
    - `reset(seed)` re-samples a new world.
    - `step(action)` moves the agent (or emits a ping) and returns a structured observation.
    """

    def __init__(self, size: int = 9, n_objects: int = 12, view_radius: int = 1):
        if size % 2 == 0:
            raise ValueError("size must be odd so the agent can start in the center")
        self.size = size
        self.n_objects = max(0, min(n_objects, size * size - 1))
        self.r = view_radius
        self._rng: random.Random
        self.grid: List[List[str]]
        self.agent: Tuple[int, int]

    # ---------------------------- helpers ----------------------------
    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def _place_objects(self) -> None:
        # Fill with empty
        self.grid = [[EMPTY for _ in range(self.size)] for _ in range(self.size)]
        # Place the agent in the center to keep things simple
        c = self.size // 2
        self.agent = (c, c)

        # Randomly place n_objects avoiding the agent cell
        used = {self.agent}
        for _ in range(self.n_objects):
            while True:
                x = self._rng.randrange(self.size)
                y = self._rng.randrange(self.size)
                if (x, y) not in used:
                    used.add((x, y))
                    break
            token = f"{self._rng.choice(COLORS)}{self._rng.choice(SHAPES)}"
            self.grid[y][x] = token

    def _view_tokens(self) -> List[List[str]]:
        vx, vy = self.agent
        r = self.r
        rows: List[List[str]] = []
        for dy in range(-r, r + 1):
            row: List[str] = []
            for dx in range(-r, r + 1):
                x, y = vx + dx, vy + dy
                if (x, y) == self.agent:
                    row.append("@")  # mark agent in view
                elif self._in_bounds(x, y):
                    row.append(self.grid[y][x])
                else:
                    row.append(" ")  # outside world
            rows.append(row)
        return rows

    def _summarize(self, view: List[List[str]]) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        uniq: List[str] = []
        for row in view:
            for t in row:
                if t in (EMPTY, "@", " "):
                    continue
                if t not in counts:
                    counts[t] = 0
                    uniq.append(t)
                counts[t] += 1
        uniq.sort()
        return {
            "unique": uniq,
            "counts": counts,
        }

    # ------------------------------ API ------------------------------
    def reset(self, seed: int) -> Dict[str, Any]:
        self._rng = random.Random(int(seed))
        self._place_objects()
        view = self._view_tokens()
        summary = self._summarize(view)
        return {
            "agent": {"x": self.agent[0], "y": self.agent[1]},
            "view": view,
            "summary": summary,
        }

    def step(self, action: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ax, ay = self.agent
        moved = False
        pinged = False
        if action == "up":
            ny = max(0, ay - 1)
            moved = ny != ay
            self.agent = (ax, ny)
        elif action == "down":
            ny = min(self.size - 1, ay + 1)
            moved = ny != ay
            self.agent = (ax, ny)
        elif action == "left":
            nx = max(0, ax - 1)
            moved = nx != ax
            self.agent = (nx, ay)
        elif action == "right":
            nx = min(self.size - 1, ax + 1)
            moved = nx != ax
            self.agent = (nx, ay)
        elif action == "ping":
            pinged = True
        # noop does nothing

        view = self._view_tokens()
        summary = self._summarize(view)
        obs = {
            "agent": {"x": self.agent[0], "y": self.agent[1]},
            "view": view,
            "summary": summary,
        }
        info = {"moved": moved, "pinged": pinged}
        return obs, info

    def render_ascii(self) -> str:
        """Full-grid ASCII render for debugging."""
        ax, ay = self.agent
        rows: List[str] = []
        for y in range(self.size):
            row: List[str] = []
            for x in range(self.size):
                if (x, y) == (ax, ay):
                    row.append("@")
                else:
                    row.append(self.grid[y][x])
            rows.append(" ".join(row))
        return "\n".join(rows)