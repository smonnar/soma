from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import random


# Tokens used elsewhere in SOMA runs (color + shape)
#   Colors: R,G,B,Y  | Shapes: ^ (tri), s (sq), o (circ)
# Examples: "G^", "Rs", "Bo", "Yo"  (seen in earlier runs)


@dataclass
class Obj:
    oid: str
    kind: str           # "chameleon" | "switch" | "door" | "pad" | "static"
    x: int
    y: int
    color: str          # 'R','G','B','Y'
    shape: str          # '^','s','o'
    state: Dict[str, float]  # arbitrary extra state

    def token(self) -> str:
        if self.kind == "door":
            return "DoorO" if self.state.get("open", 0.0) >= 1.0 else "DoorC"
        if self.kind == "pad":
            return f"Pad{self.color}"
        if self.kind == "switch":
            return "SW"
        # chameleon & static show as color+shape
        return f"{self.color}{self.shape}"


class GridWorldV1:
    """GridWorld v1.5 — persistent objects + simple causal puzzles.

    Additions vs v0:
      - Persistent objects with IDs and state.
      - Chameleon object: changes color when pinged nearby.
      - Door (blocks movement when closed) + pads (G then R within a time window opens the door), and a switch that toggles door.
      - Summary exposes tokens so planner/channel can notice contradictions & pattern completion opportunities.
    """

    ACTIONS = ["up", "down", "left", "right", "noop", "ping"]

    def __init__(self, size: int = 9, n_objects: int = 14, view_radius: int = 1):
        self.size = int(size)
        self.view_radius = int(view_radius)
        self.n_objects = int(n_objects)
        self.rng = random.Random(0)
        self.tick = 0
        self.agent = {"x": 0, "y": 0}
        self.objects: Dict[str, Obj] = {}
        self._pads_window = 8      # ticks
        self._pads_seq: List[Tuple[int, str]] = []  # (tick, color)

    # ---------------- core API ----------------
    def reset(self, seed: int) -> Dict:
        self.rng = random.Random(int(seed))
        self.tick = 0
        self.agent = {"x": self.size // 2, "y": self.size // 2}
        self.objects = {}
        self._pads_seq.clear()

        # Place a door roughly mid-top; blocks movement when closed
        door = Obj(
            oid="door0", kind="door",
            x=self.size // 2, y=max(1, self.size // 3 - 1),
            color="B", shape="s", state={"open": 0.0, "timer": 0}
        )
        self.objects[door.oid] = door

        # Two pads: G then R sequence opens door for a while
        pg = self._place_any("pad", color="G", shape="o")
        pr = self._place_any("pad", color="R", shape="o")
        self.objects[pg.oid] = pg
        self.objects[pr.oid] = pr

        # A switch near the agent toggles the door when pinged
        sw = self._place_any("switch", color="Y", shape="s")
        self.objects[sw.oid] = sw

        # One chameleon (color cycle R->G->B->Y)
        ch = self._place_any("chameleon", color=self.rng.choice(["R","G","B","Y"]), shape=self.rng.choice(["^","s","o"]))
        ch.state["cycle"] = 1
        self.objects[ch.oid] = ch

        # Distractors (static)
        for _ in range(max(0, self.n_objects - len(self.objects))):
            o = self._place_any("static", color=self.rng.choice(["R","G","B","Y"]), shape=self.rng.choice(["^","s","o"]))
            self.objects[o.oid] = o

        return self._observe()

    def step(self, action: str) -> Tuple[Dict, Dict]:
        action = str(action)
        info: Dict = {"interactions": []}

        # Movement proposal
        nx, ny = self.agent["x"], self.agent["y"]
        if action == "up":
            ny = max(0, ny - 1)
        elif action == "down":
            ny = min(self.size - 1, ny + 1)
        elif action == "left":
            nx = max(0, nx - 1)
        elif action == "right":
            nx = min(self.size - 1, nx + 1)
        elif action in ("noop", "ping"):
            pass

        # Block by door if closed
        if not self._is_blocked(nx, ny):
            self.agent["x"], self.agent["y"] = nx, ny

        # Pad sequence check (standing "on" a pad counts)
        on_pad = self._pad_at(self.agent["x"], self.agent["y"])  # returns 'G'/'R'/None
        if on_pad:
            self._pads_seq.append((self.tick, on_pad))
            self._trim_pads_seq()
            if self._sequence_is_gr():
                self._open_door(ticks=12)
                info["interactions"].append({"kind": "pads_open", "at": self.tick})

        # Ping interactions (radius 1 Manhattan)
        if action == "ping":
            for o in self._nearby_objects(radius=1):
                if o.kind == "switch":
                    self._open_door(ticks=8)
                    info["interactions"].append({"kind": "switch_toggle", "oid": o.oid})
                elif o.kind == "chameleon":
                    self._advance_color(o)
                    info["interactions"].append({"kind": "chameleon_flip", "oid": o.oid, "color": o.color})

        # Door timer ticks down
        d = self._get_door()
        if d.state.get("timer", 0) > 0:
            d.state["timer"] -= 1
            if d.state["timer"] <= 0:
                d.state["open"] = 0.0

        # Occasional distractor drift (tiny, to spice scenes)
        self._distractor_drift()

        self.tick += 1
        return self._observe(), info

    # ---------------- helpers ----------------
    def _place_any(self, kind: str, color: str, shape: str) -> Obj:
        while True:
            x = self.rng.randrange(self.size)
            y = self.rng.randrange(self.size)
            # avoid agent spawn & door cell
            if (x, y) == (self.agent["x"], self.agent["y"]):
                continue
            if self._door_coords() == (x, y):
                continue
            if any((o.x, o.y) == (x, y) for o in self.objects.values()):
                continue
            oid = f"{kind}{len([k for k in self.objects if k.startswith(kind)])}"
            return Obj(oid=oid, kind=kind, x=x, y=y, color=color, shape=shape, state={})

    def _door_coords(self) -> Tuple[int, int]:
        d = self._get_door()
        return (d.x, d.y)

    def _get_door(self) -> Obj:
        for o in self.objects.values():
            if o.kind == "door":
                return o
        # Should not happen
        raise RuntimeError("door not found")

    def _open_door(self, ticks: int) -> None:
        d = self._get_door()
        d.state["open"] = 1.0
        d.state["timer"] = int(max(d.state.get("timer", 0), ticks))

    def _is_blocked(self, x: int, y: int) -> bool:
        dx, dy = self._door_coords()
        if (x, y) == (dx, dy):
            return self._get_door().state.get("open", 0.0) < 1.0
        return False

    def _pad_at(self, x: int, y: int) -> Optional[str]:
        for o in self.objects.values():
            if o.kind == "pad" and (o.x, o.y) == (x, y):
                return o.color
        return None

    def _nearby_objects(self, radius: int = 1) -> List[Obj]:
        ax, ay = self.agent["x"], self.agent["y"]
        out: List[Obj] = []
        for o in self.objects.values():
            if abs(o.x - ax) + abs(o.y - ay) <= radius:
                out.append(o)
        return out

    def _trim_pads_seq(self) -> None:
        cutoff = self.tick - self._pads_window
        self._pads_seq = [(t, c) for (t, c) in self._pads_seq if t >= cutoff]

    def _sequence_is_gr(self) -> bool:
        # True if last seen distinct pads within window form G then R
        colors = [c for (_, c) in self._pads_seq]
        # compress repeats
        comp: List[str] = []
        for c in colors:
            if not comp or comp[-1] != c:
                comp.append(c)
        if len(comp) < 2:
            return False
        return comp[-2:] == ["G", "R"]

    def _advance_color(self, o: Obj) -> None:
        order = ["R", "G", "B", "Y"]
        i = order.index(o.color)
        o.color = order[(i + int(o.state.get("cycle", 1))) % len(order)]

    def _distractor_drift(self) -> None:
        # Small random color flip on a random static to increase variety
        if self.rng.random() < 0.10:  # 10% per tick
            stats = [o for o in self.objects.values() if o.kind == "static"]
            if not stats:
                return
            o = self.rng.choice(stats)
            self._advance_color(o)

    # ---------------- observation ----------------
    def _observe(self) -> Dict:
        ax, ay = self.agent["x"], self.agent["y"]

        # Build a local view grid (square) centered on agent with side 2*view_radius+1
        R = int(self.view_radius)
        view: List[List[str]] = []
        uniq: List[str] = []

        for dy in range(-R, R + 1):
            row: List[str] = []
            for dx in range(-R, R + 1):
                x = ax + dx
                y = ay + dy
                row.append(self._token_at(x, y))
            view.append(row)

        # Unique tokens visible (exclude blanks)
        for row in view:
            for t in row:
                if t:
                    uniq.append(t)

        summary = {
            "unique": sorted(set(uniq)),
        }
        return {
            "agent": {"x": ax, "y": ay},
            "view": view,          # <--- REQUIRED by perception/features.py
            "summary": summary,
        }

    def _token_at(self, x: int, y: int) -> str:
        # Out of bounds = blank
        if x < 0 or y < 0 or x >= self.size or y >= self.size:
            return ""
        for o in self.objects.values():
            if (o.x, o.y) == (x, y):
                return o.token()
        return ""