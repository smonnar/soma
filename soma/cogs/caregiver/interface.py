from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set
import json

from soma.cogs.self_notes.notes import SelfNotes


@dataclass
class Query:
    qid: str
    tick: int
    tokens: List[str]
    context: Dict[str, Any]


class CaregiverInterface:
    """Writes SOMA queries and ingests caregiver answers (tags).

    Files in run_dir:
      - caregiver_queries.jsonl : SOMA -> caregiver
      - caregiver_answers.jsonl : caregiver -> SOMA
      - caregiver_tags.json     : latest merged tags { token: gloss }
    """

    def __init__(self, run_dir: Path, notes: SelfNotes, run_id: str) -> None:
        self.run_dir = Path(run_dir)
        self.notes = notes
        self.run_id = str(run_id)
        self.path_q = self.run_dir / "caregiver_queries.jsonl"
        self.path_a = self.run_dir / "caregiver_answers.jsonl"
        self.path_tags = self.run_dir / "caregiver_tags.json"
        self._asked_ticks: Set[int] = set()
        self.tags: Dict[str, str] = {}
        if self.path_tags.exists():
            try:
                self.tags = json.loads(self.path_tags.read_text(encoding="utf-8"))
            except Exception:
                self.tags = {}

    # ---------------- write query ----------------
    def maybe_query(self, *, tick: int, tokens: List[str], context: Dict[str, Any]) -> None:
        if not tokens:
            return
        # Only query on interesting symbols and avoid duplicate per tick
        interesting = [t for t in tokens if t in {"?", "N!", "N↑", "Over!"}]
        if not interesting:
            return
        if tick in self._asked_ticks:
            return
        self._asked_ticks.add(tick)

        q = {
            "qid": f"{self.run_id}:{tick}",
            "tick": tick,
            "tokens": interesting,
            "context": context,
        }
        with self.path_q.open("a", encoding="utf-8") as f:
            f.write(json.dumps(q) + "\n")

        self.notes.note(
            kind="query",
            payload={"tick": tick, "tokens": interesting, "prompt": "caregiver_gloss"},
            tick=tick,
        )

    # ---------------- ingest answers ----------------
    def poll_answers(self) -> Dict[str, str]:
        """Read all answers file and merge tags; return new tags added this poll."""
        if not self.path_a.exists():
            return {}
        new_tags: Dict[str, str] = {}
        try:
            with self.path_a.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    # answer format: { qid, tick, tags: { token: gloss }, note?: str }
                    tags = obj.get("tags", {}) or {}
                    for k, v in tags.items():
                        k = str(k)
                        v = str(v)
                        if self.tags.get(k) != v:
                            self.tags[k] = v
                            new_tags[k] = v
        except Exception:
            return {}

        if new_tags:
            # persist and note
            self.path_tags.write_text(json.dumps(self.tags, indent=2), encoding="utf-8")
            self.notes.note(
                kind="caregiver_tag",
                payload={"tags": new_tags},
                tick=max(0, obj.get("tick", 0) if isinstance(obj, dict) else 0),
            )
        return new_tags