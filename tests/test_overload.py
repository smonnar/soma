from __future__ import annotations

import unittest

from soma.cogs.reflex.reflex import ReflexManager


class _NotesStub:
    def note(self, *args, **kwargs):
        pass


class TestOverloadReflex(unittest.TestCase):
    def test_overload_triggers_noop(self):
        rm = ReflexManager(notes=_NotesStub(), overload_unique_threshold=3)
        action, triggers = rm.advise(
            tick=10,
            selected="right",
            unique_tokens=["A", "B", "C", "D"],
        )
        self.assertEqual(action, "noop")
        self.assertIn("overload", triggers)


if __name__ == "__main__":
    unittest.main()