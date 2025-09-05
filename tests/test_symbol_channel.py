from __future__ import annotations

import unittest

from soma.cogs.channel.symbolic import SymbolicChannel


class _NotesStub:
    def note(self, *args, **kwargs):
        pass


class TestSymbolicChannel(unittest.TestCase):
    def test_emits_novelty_symbol(self):
        ch = SymbolicChannel(notes=_NotesStub())
        tokens, gloss, _ = ch.maybe_emit(
            tick=0,
            novelty=1.0,
            boredom=0.0,
            matches=[],
            summary={"unique": []},
            drives={"curiosity": 1.0, "stability": 0.0},
            dominant="curiosity",
            noop_streak=0,
            reflex_triggers=[],
        )
        self.assertIn("N!", tokens)


if __name__ == "__main__":
    unittest.main()