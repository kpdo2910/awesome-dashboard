#!/usr/bin/env python3
"""Auto-grade rule tests — run from the add-on root:

    python3 tools/test_autograde.py

`features/autograde/rules` never imports `aqt`, so it loads directly. Keep it
that way; `controller.py` is where anything needing Anki belongs.
"""

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "awd_autograde_rules", ROOT / "features" / "autograde" / "rules.py"
)
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

ALL = [1, 2, 3, 4]
DEFAULT = rules.global_settings({})


class ThresholdTests(unittest.TestCase):
    """5 / 10 / 15 by default; each boundary belongs to the faster band."""

    def test_bands(self):
        for seconds, zone in (
            (0, "easy"), (4.9, "easy"), (5.0, "easy"),
            (5.1, "good"), (10.0, "good"),
            (10.1, "hard"), (15.0, "hard"),
            (15.1, "again"), (600, "again"),
        ):
            with self.subTest(seconds=seconds):
                self.assertEqual(rules.zone_for(seconds * 1000, DEFAULT), zone)

    def test_grade_maps_zone_to_ease(self):
        for seconds, ease in ((1, 4), (7, 3), (12, 2), (20, 1)):
            with self.subTest(seconds=seconds):
                self.assertEqual(rules.grade(seconds * 1000, DEFAULT, ALL)[0], ease)

    def test_negative_elapsed_is_the_fastest_band(self):
        self.assertEqual(rules.zone_for(-5000, DEFAULT), "easy")


class ClampTests(unittest.TestCase):
    """Fewer than four buttons must never cost the user a recall."""

    def test_missing_hard_folds_up_into_good(self):
        # Three-button card: Again / Good / Easy.
        ease, zone = rules.grade(12000, DEFAULT, [1, 3, 4])
        self.assertEqual(zone, "hard")
        self.assertEqual(ease, 3)

    def test_missing_easy_folds_down_into_good(self):
        self.assertEqual(rules.clamp(rules.EASY, [1, 3]), 3)

    def test_two_button_card(self):
        self.assertEqual(rules.grade(1000, DEFAULT, [1, 3])[0], 3)
        self.assertEqual(rules.grade(99000, DEFAULT, [1, 3])[0], 1)

    def test_again_survives_everything(self):
        self.assertEqual(rules.failed(ALL), 1)
        self.assertEqual(rules.failed([1, 3]), 1)

    def test_empty_button_list_is_again(self):
        self.assertEqual(rules.clamp(rules.EASY, []), 1)


class NormaliseTests(unittest.TestCase):
    """A hand-edited config must not make a whole band unreachable."""

    def test_out_of_order_is_pushed_apart(self):
        clean = rules.normalise({"easyMax": 30, "goodMax": 5, "hardMax": 1})
        self.assertEqual((clean["easyMax"], clean["goodMax"], clean["hardMax"]),
                         (30, 31, 32))

    def test_junk_falls_back_to_defaults(self):
        clean = rules.normalise({"easyMax": "abc", "goodMax": None})
        self.assertEqual(clean["easyMax"], rules.DEFAULTS["easyMax"])
        self.assertEqual(clean["goodMax"], rules.DEFAULTS["goodMax"])

    def test_equal_values_are_separated(self):
        clean = rules.normalise({"easyMax": 5, "goodMax": 5, "hardMax": 5})
        self.assertEqual((clean["goodMax"], clean["hardMax"]), (6, 7))


class ResolveTests(unittest.TestCase):
    """Per-deck overrides are partial and inherit down the tree, root first."""

    def test_no_entry_uses_the_global(self):
        config = {"autoGrade": True, "autoGradeEasyMax": 3}
        settings = rules.resolve(config, [1, 2])
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["easyMax"], 3)

    def test_child_inherits_the_parents_thresholds(self):
        config = {
            "autoGrade": False,
            "autoGradeDecks": {
                "1": {"enabled": True, "easyMax": 2, "goodMax": 4, "hardMax": 6},
                "2": {"enabled": True},
            },
        }
        settings = rules.resolve(config, [1, 2])
        self.assertEqual(settings["easyMax"], 2)
        self.assertEqual(settings["hardMax"], 6)

    def test_child_overrides_only_what_it_names(self):
        config = {
            "autoGradeDecks": {
                "1": {"enabled": True, "easyMax": 2},
                "2": {"easyMax": 8},
            },
        }
        settings = rules.resolve(config, [1, 2])
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["easyMax"], 8)

    def test_child_can_switch_itself_off(self):
        config = {
            "autoGrade": True,
            "autoGradeDecks": {"2": {"enabled": False}},
        }
        self.assertFalse(rules.resolve(config, [1, 2])["enabled"])

    def test_junk_override_is_ignored(self):
        config = {"autoGrade": True, "autoGradeDecks": {"1": "yes"}}
        self.assertTrue(rules.resolve(config, [1])["enabled"])

    def test_unknown_keys_do_not_leak_through(self):
        config = {"autoGradeDecks": {"1": {"confirmSeconds": 4}}}
        self.assertNotIn("confirmSeconds", rules.resolve(config, [1]))


class BandTests(unittest.TestCase):
    """The bar is drawn from the same numbers that pick the grade."""

    def test_widths_cover_the_whole_bar(self):
        for settings in (DEFAULT, rules.normalise({"easyMax": 1, "goodMax": 2,
                                                   "hardMax": 30})):
            with self.subTest(settings=settings):
                total = sum(width for _zone, width in rules.bands(settings))
                self.assertAlmostEqual(total, 100.0, places=2)

    def test_order_is_easy_good_hard(self):
        self.assertEqual([zone for zone, _ in rules.bands(DEFAULT)],
                         ["easy", "good", "hard"])


class ConsistencyTests(unittest.TestCase):
    """The bar running out and the grade saying Again are the same event."""

    def test_bar_end_is_the_again_boundary(self):
        settings = rules.normalise({"easyMax": 2, "goodMax": 4, "hardMax": 9})
        self.assertEqual(rules.zone_for(9000, settings), "hard")
        self.assertEqual(rules.zone_for(9001, settings), "again")

    def test_every_band_is_reachable(self):
        settings = rules.normalise({"easyMax": 1, "goodMax": 2, "hardMax": 3})
        seen = {rules.zone_for(ms, settings)
                for ms in range(0, 5000, 100)}
        self.assertEqual(seen, {"easy", "good", "hard", "again"})


if __name__ == "__main__":
    unittest.main(verbosity=1)
