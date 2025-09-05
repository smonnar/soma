from __future__ import annotations

import unittest

from soma.cogs.curiosity.curiosity import CuriosityEngine
from soma.cogs.memory.memory import MemorySystem


class _NotesStub:
    def note(self, *args, **kwargs):
        pass


class TestNovelty(unittest.TestCase):
    def test_high_novelty_when_no_matches(self):
        cur = CuriosityEngine(notes=_NotesStub(), novelty_threshold=0.6, top_k=3)
        mem = MemorySystem(dim=8, max_items=16)
        summary = {"unique": ["new"]}
        out = cur.assess(tick=0, summary=summary, matches=[], memory=mem)
        self.assertGreaterEqual(out.get("novelty", 0.0), 0.9)


if __name__ == "__main__":
    unittest.main()