#!/usr/bin/env python3
"""Dashboard layout unit tests — run from the add-on root:

    python3 tools/test_layout.py

`features/layout.py` never imports `aqt`, which is the only reason this runs
outside Anki. Keep it that way.
"""

import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

_pkg = types.ModuleType("awd_features")
_pkg.__path__ = [str(ROOT / "features")]
sys.modules["awd_features"] = _pkg

from awd_features import layout  # noqa: E402


class DefaultTests(unittest.TestCase):
    def test_every_widget_once_in_default_order(self):
        ids = [e["id"] for e in layout.default()]
        self.assertEqual(ids, list(layout.ORDER))
        self.assertEqual(len(set(ids)), len(ids))

    def test_default_sizes_are_allowed_and_fill_rows(self):
        for entry in layout.default():
            allowed, fallback = layout.WIDGETS[entry["id"]]
            self.assertIn(entry["size"], allowed)
            self.assertEqual(entry["size"], fallback)
            self.assertFalse(entry["hidden"])
        # Five fifths, then two thirds plus a third: the shipping dashboard.
        by_id = {e["id"]: e["size"] for e in layout.default()}
        self.assertEqual([by_id[s] for s in layout.STATS], ["xs"] * 5)
        self.assertEqual((by_id["heatmap"], by_id["pomodoro"]), ("m", "s"))


class NormalizeTests(unittest.TestCase):
    def test_keeps_order_and_appends_missing(self):
        out = layout.normalize([{"id": "decks", "size": "l"}, {"id": "heatmap", "size": "l"}])
        ids = [e["id"] for e in out]
        self.assertEqual(ids[:2], ["decks", "heatmap"])
        self.assertEqual(set(ids), set(layout.ORDER))
        self.assertEqual(len(ids), len(layout.ORDER))

    def test_drops_unknown_and_duplicates(self):
        out = layout.normalize([
            {"id": "ghost", "size": "l"},
            {"id": "pomodoro", "size": "m", "hidden": True},
            {"id": "pomodoro", "size": "s"},
            "junk",
            {"size": "m"},
        ])
        pom = [e for e in out if e["id"] == "pomodoro"]
        self.assertEqual(len(pom), 1)
        self.assertEqual(pom[0], {"id": "pomodoro", "size": "m", "hidden": True})
        self.assertNotIn("ghost", [e["id"] for e in out])

    def test_size_falls_back_when_not_offered(self):
        out = layout.normalize([{"id": "studied", "size": "l"}, {"id": "habits", "size": "xs"}])
        by_id = {e["id"]: e["size"] for e in out}
        self.assertEqual(by_id["studied"], "xs")
        self.assertEqual(by_id["habits"], "l")

    def test_hidden_is_coerced_to_bool(self):
        out = layout.normalize([{"id": "decks", "hidden": 1}, {"id": "habits", "hidden": None}])
        by_id = {e["id"]: e["hidden"] for e in out}
        self.assertIs(by_id["decks"], True)
        self.assertIs(by_id["habits"], False)

    def test_garbage_is_the_default(self):
        for raw in (None, "x", 3, {}, [None, 4]):
            self.assertEqual(layout.normalize(raw), layout.default())

    def test_idempotent(self):
        once = layout.normalize([{"id": "due", "size": "s", "hidden": True}, {"id": "decks"}])
        self.assertEqual(layout.normalize(once), once)


class ConfigTests(unittest.TestCase):
    def test_stored_layout_wins_over_legacy_flags(self):
        config = {"dashboardLayout": [{"id": "heatmap", "size": "l"}], "showHeatmap": False}
        out = layout.from_config(config)
        self.assertFalse(layout.is_hidden(out, "heatmap"))
        self.assertEqual(out[0]["id"], "heatmap")

    def test_legacy_flags_migrate_when_no_layout(self):
        out = layout.from_config({"showStats": False, "showPomodoro": False, "showHabits": True})
        for stat in layout.STATS:
            self.assertTrue(layout.is_hidden(out, stat))
        self.assertTrue(layout.is_hidden(out, "pomodoro"))
        self.assertFalse(layout.is_hidden(out, "habits"))
        self.assertFalse(layout.is_hidden(out, "heatmap"))

    def test_no_config_is_the_default(self):
        self.assertEqual(layout.from_config({}), layout.default())
        self.assertEqual(layout.from_config({"dashboardLayout": None}), layout.default())

    def test_group_visibility(self):
        out = layout.default()
        layout.set_hidden(out, layout.STATS, True)
        self.assertFalse(layout.any_visible(out, layout.STATS))
        layout.set_hidden(out, ("streak",), False)
        self.assertTrue(layout.any_visible(out, layout.STATS))

    def test_strip_legacy(self):
        config = {"showStats": False, "showHabits": True, "theme": "glass"}
        layout.strip_legacy(config)
        self.assertEqual(config, {"theme": "glass"})


if __name__ == "__main__":
    unittest.main()
