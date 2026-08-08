#!/usr/bin/env python3
"""Habit tracker unit tests — run from the add-on root:

    python3 tools/test_habits.py

Anki cannot be imported outside Anki, so `features/habits` is loaded as a
standalone package under a synthetic name and `aqt` is stubbed. That works
because `models`, `scheduling` and `stats` never import `aqt` at all, and
`store` only reaches for it inside methods. Keep it that way: the moment one of
them grows a module-level `from aqt import mw`, this file stops running and the
only logic in the add-on with real edge cases goes untested.

With no `aqt.qt` to import, the store's debounce falls back to writing
synchronously, so a flush is observable right after the call that dirtied it.
"""

import copy
import pathlib
import sys
import types
import unittest
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent

_aqt = types.ModuleType("aqt")
_aqt.mw = types.SimpleNamespace(col=None)
sys.modules.setdefault("aqt", _aqt)

_pkg = types.ModuleType("awd_habits")
_pkg.__path__ = [str(ROOT / "features" / "habits")]
sys.modules["awd_habits"] = _pkg

from awd_habits import models, report, scheduling, stats, store  # noqa: E402

D = scheduling.from_date


def habit(**fields):
    fields.setdefault("id", "h_test")
    fields.setdefault("name", "Test")
    fields.setdefault("created", 20260101)
    return models.Habit(**fields)


def daily(**fields):
    return habit(schedule={"kind": "daily"}, **fields)


def weekdays(days, **fields):
    return habit(schedule={"kind": "weekdays", "days": days}, **fields)


def weekly(n, **fields):
    return habit(schedule={"kind": "times_per_week", "n": n}, **fields)


class FakeCol:
    """Just enough collection for HabitStore: config get/set and a day cutoff."""

    def __init__(self, cutoff: float):
        self.conf = {}
        self.sched = types.SimpleNamespace(day_cutoff=cutoff)
        self.writes = 0

    def get_config(self, key, default=None):
        # Deep copies both ways, like the real backend — otherwise the store's
        # cache and the "stored" blob are the same object and a missing flush
        # would still look like it worked.
        return copy.deepcopy(self.conf.get(key, default))

    def set_config(self, key, val, undoable=False):
        self.writes += 1
        self.conf[key] = copy.deepcopy(val)


def cutoff_for(year, month, day, hour=4):
    """Anki's day_cutoff for the Anki day *before* the given wall time."""
    return datetime(year, month, day, hour).timestamp()


# --- models ----------------------------------------------------------------------

class ModelTests(unittest.TestCase):
    def test_binary_target_is_always_one(self):
        h = models.Habit(name="x", kind="binary", target=9)
        self.assertEqual(h.target, 1)
        self.assertEqual(h.unit, "")

    def test_count_keeps_target_and_unit(self):
        h = models.Habit(name="x", kind="count", target=3000, unit="ml")
        self.assertEqual(h.target, 3000)
        self.assertEqual(h.unit, "ml")

    def test_broken_schedule_falls_back_to_daily(self):
        self.assertEqual(models.normalise_schedule(None), {"kind": "daily"})
        self.assertEqual(models.normalise_schedule({"kind": "weekdays", "days": []}),
                         {"kind": "daily"})
        self.assertEqual(models.normalise_schedule({"kind": "weekdays", "days": [9, 2, 2]}),
                         {"kind": "weekdays", "days": [2]})
        self.assertEqual(models.normalise_schedule({"kind": "times_per_week"}),
                         {"kind": "times_per_week", "n": 3})

    def test_round_trip(self):
        h = models.Habit(name="Read", kind="count", target=30, unit="min",
                         schedule={"kind": "weekdays", "days": [1, 3, 5]})
        again = models.Habit.from_dict(h.to_dict())
        self.assertEqual(again.to_dict(), h.to_dict())

    def test_unusable_records_are_dropped_not_fatal(self):
        self.assertIsNone(models.Habit.from_dict({"id": "x"}))       # no name
        self.assertIsNone(models.Habit.from_dict({"name": "x"}))     # no id
        self.assertIsNone(models.Habit.from_dict("nonsense"))

    def test_step_scales_with_target(self):
        self.assertEqual(models.Habit(name="x", kind="count", target=10).step(), 1)
        self.assertEqual(models.Habit(name="x", kind="count", target=3000).step(), 250)
        self.assertEqual(models.Habit(name="x", kind="binary").step(), 1)

    def test_migrate_keeps_a_newer_version_number(self):
        self.assertEqual(models.migrate({})["v"], models.META_VERSION)
        self.assertEqual(models.migrate({"v": 99, "habits": []})["v"], 99)
        self.assertEqual(models.migrate("junk"), models.empty_meta())


# --- scheduling -------------------------------------------------------------------

class SchedulingTests(unittest.TestCase):
    def test_day_arithmetic_crosses_boundaries(self):
        self.assertEqual(scheduling.shift(20261231, 1), 20270101)
        self.assertEqual(scheduling.shift(20260301, -1), 20260228)
        self.assertEqual(scheduling.shift(20240301, -1), 20240229)  # leap year
        self.assertEqual(scheduling.days_between(20260101, 20260201), 31)

    def test_today_uses_the_rollover_not_the_calendar(self):
        # 2am on the 9th, with the rollover at 4am, is still the 8th.
        cutoff = cutoff_for(2026, 8, 9)
        self.assertEqual(scheduling.today_from_cutoff(cutoff), 20260808)

    def test_week_bounds_follow_the_first_weekday(self):
        wednesday = 20260812
        self.assertEqual(scheduling.week_bounds(wednesday, scheduling.MONDAY),
                         (20260810, 20260816))
        self.assertEqual(scheduling.week_bounds(wednesday, scheduling.SUNDAY),
                         (20260809, 20260815))

    def test_month_and_year_bounds(self):
        self.assertEqual(scheduling.month_bounds(20260215), (20260201, 20260228))
        self.assertEqual(scheduling.month_bounds(20240215), (20240201, 20240229))
        self.assertEqual(scheduling.year_bounds(20260615), (20260101, 20261231))

    def test_add_months_clamps_to_the_shorter_month(self):
        self.assertEqual(scheduling.add_months(20260131, 1), 20260228)
        self.assertEqual(scheduling.add_months(20261215, 1), 20270115)
        self.assertEqual(scheduling.add_months(20260115, -1), 20251215)

    def test_is_due_per_schedule(self):
        monday, saturday = 20260810, 20260815
        self.assertTrue(scheduling.is_due(daily(), saturday))
        self.assertTrue(scheduling.is_due(weekdays([1, 2, 3, 4, 5]), monday))
        self.assertFalse(scheduling.is_due(weekdays([1, 2, 3, 4, 5]), saturday))
        # Every day is a chance to make one of the week's repetitions.
        self.assertTrue(scheduling.is_due(weekly(3), saturday))
        self.assertTrue(scheduling.is_weekly(weekly(3)))
        self.assertFalse(scheduling.is_weekly(daily()))

    def test_scheduled_days_never_reach_past_today(self):
        days = scheduling.scheduled_days(daily(), 20260801, 20260831, today=20260805)
        self.assertEqual(days[-1], 20260805)

    def test_scheduled_days_respect_creation_and_archive(self):
        h = daily(created=20260803, archived=True, archived_at=20260806)
        days = scheduling.scheduled_days(h, 20260801, 20260810, today=20260810)
        self.assertEqual(days, [20260803, 20260804, 20260805, 20260806])


# --- stats ---------------------------------------------------------------------------

class StreakTests(unittest.TestCase):
    def test_daily_streak_counts_back_from_today(self):
        values = {20260806: 1, 20260807: 1, 20260808: 1}
        result = stats.streaks(daily(), values, today=20260808)
        self.assertEqual(result["current"], 3)
        self.assertEqual(result["longest"], 3)

    def test_today_undone_does_not_break_the_streak(self):
        values = {20260806: 1, 20260807: 1}
        result = stats.streaks(daily(), values, today=20260808)
        self.assertEqual(result["current"], 2)

    def test_yesterday_undone_does(self):
        values = {20260806: 1, 20260808: 1}
        result = stats.streaks(daily(), values, today=20260808)
        self.assertEqual(result["current"], 1)
        self.assertEqual(result["longest"], 1)

    def test_weekend_is_skipped_not_missed(self):
        # Fri 7th, Mon 10th — the weekend between them is not scheduled.
        h = weekdays([1, 2, 3, 4, 5])
        values = {20260806: 1, 20260807: 1, 20260810: 1}
        result = stats.streaks(h, values, today=20260810)
        self.assertEqual(result["current"], 3)

    def test_count_habit_needs_the_whole_target(self):
        h = daily(kind="count", target=3, unit="km")
        values = {20260807: 3, 20260808: 1}
        result = stats.streaks(h, values, today=20260808)
        # Today is short of target, but the day is not over.
        self.assertEqual(result["current"], 1)

    def test_longest_survives_a_later_gap(self):
        values = {d: 1 for d in (20260801, 20260802, 20260803, 20260804, 20260807)}
        result = stats.streaks(daily(created=20260801), values, today=20260808)
        self.assertEqual(result["longest"], 4)
        # Today is still open, so the current run is the one through yesterday.
        self.assertEqual(result["current"], 1)

    def test_a_missed_yesterday_zeroes_the_current_run(self):
        values = {d: 1 for d in (20260801, 20260802, 20260803, 20260804)}
        result = stats.streaks(daily(created=20260801), values, today=20260808)
        self.assertEqual(result["longest"], 4)
        self.assertEqual(result["current"], 0)

    def test_current_never_exceeds_longest(self):
        values = {20260807: 1, 20260808: 1}
        result = stats.streaks(daily(created=20260807), values, today=20260808)
        self.assertLessEqual(result["current"], result["longest"])

    def test_weekly_streak_counts_weeks_not_days(self):
        h = weekly(3, created=20260727)  # Monday
        values = {}
        for week_start in (20260727, 20260803):
            for offset in (0, 2, 4):
                values[scheduling.shift(week_start, offset)] = 1
        result = stats.streaks(h, values, today=20260808, first_day=scheduling.MONDAY)
        self.assertTrue(result["weekly"])
        self.assertEqual(result["current"], 2)

    def test_weekly_week_in_progress_is_not_a_failure(self):
        h = weekly(3, created=20260727)
        values = {20260727: 1, 20260729: 1, 20260731: 1, 20260803: 1}
        # One done so far this week; last week was complete.
        result = stats.streaks(h, values, today=20260804, first_day=scheduling.MONDAY)
        self.assertEqual(result["current"], 1)


class CompletionTests(unittest.TestCase):
    def test_daily_rate(self):
        values = {20260801: 1, 20260803: 1}
        result = stats.completion(daily(created=20260801), values,
                                  20260801, 20260804, today=20260804)
        self.assertEqual((result["done"], result["due"]), (2, 4))
        self.assertAlmostEqual(result["rate"], 0.5)

    def test_future_days_are_not_owed(self):
        result = stats.completion(daily(created=20260801), {},
                                  20260801, 20260831, today=20260803)
        self.assertEqual(result["due"], 3)

    def test_weekdays_rate_ignores_the_weekend(self):
        h = weekdays([1, 2, 3, 4, 5], created=20260803)
        result = stats.completion(h, {}, 20260803, 20260809, today=20260809)
        self.assertEqual(result["due"], 5)

    def test_weekly_rate_is_measured_in_repetitions(self):
        h = weekly(3, created=20260727)
        values = {20260727: 1, 20260729: 1}       # 2 of 3 in a finished week
        result = stats.completion(h, values, 20260727, 20260809,
                                  today=20260809, first_day=scheduling.MONDAY)
        self.assertTrue(result["weekly"])
        self.assertEqual((result["done"], result["due"]), (2, 3))

    def test_weekly_current_week_is_reported_separately(self):
        h = weekly(3, created=20260727)
        values = {20260803: 1}
        result = stats.completion(h, values, 20260727, 20260809,
                                  today=20260805, first_day=scheduling.MONDAY)
        self.assertEqual(result["in_progress"], {"done": 1, "target": 3})
        self.assertEqual(result["due"], 3)        # only the finished week

    def test_partial_first_week_is_not_owed(self):
        h = weekly(3, created=20260731)           # created on a Friday
        result = stats.completion(h, {}, 20260727, 20260802,
                                  today=20260809, first_day=scheduling.MONDAY)
        self.assertEqual(result["due"], 0)

    def test_totals_and_weekday_rates(self):
        h = daily(kind="count", target=10, created=20260803)
        values = {20260803: 10, 20260804: 4, 20260805: 10}
        totals = stats.totals(h, values, 20260803, 20260809, today=20260809)
        self.assertEqual(totals, {"days_done": 2, "amount": 24})
        rates = stats.weekday_rates(h, values, 20260803, 20260809, today=20260809)
        self.assertEqual(rates[0], 1.0)           # Monday done
        self.assertEqual(rates[1], 0.0)           # Tuesday short of target
        self.assertEqual(len(rates), 7)

    def test_weekday_rates_are_none_where_never_scheduled(self):
        rates = stats.weekday_rates(weekdays([1], created=20260803), {},
                                    20260803, 20260809, today=20260809)
        self.assertIsNone(rates[5])

    def test_day_summary_counts_only_habits_due_that_day(self):
        habits = [
            daily(id="a"),
            weekdays([1, 2, 3, 4, 5], id="b"),
            weekly(2, id="c"),
        ]
        saturday = 20260815
        summary = stats.day_summary(habits, {"a": 1}, saturday)
        self.assertEqual(summary, {"done": 1, "due": 2})

    def test_day_summary_counts_a_finished_week_as_done(self):
        habits = [weekly(2, id="c")]
        saturday = 20260815
        self.assertEqual(stats.day_summary(habits, {}, saturday, {"c": 2}),
                         {"done": 1, "due": 1})
        self.assertEqual(stats.day_summary(habits, {}, saturday, {"c": 1}),
                         {"done": 0, "due": 1})


# --- store ---------------------------------------------------------------------------

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.col = FakeCol(cutoff_for(2026, 8, 9))   # "today" is 2026-08-08
        _aqt.mw.col = self.col
        self.store = store.HabitStore()

    def tearDown(self):
        _aqt.mw.col = None

    def add(self, **fields):
        fields.setdefault("name", "Read")
        return self.store.add(models.Habit(**fields))

    def test_today_follows_the_rollover(self):
        self.assertEqual(self.store.today(), 20260808)

    def test_add_assigns_id_created_and_position(self):
        first = self.add(name="A")
        second = self.add(name="B")
        self.assertTrue(first.id.startswith("h_"))
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.created, 20260808)
        self.assertEqual([h.pos for h in self.store.habits()], [0, 1])

    def test_toggle_writes_a_sparse_log(self):
        h = self.add()
        self.assertEqual(self.store.toggle(h.id, 20260808), 1)
        self.assertEqual(self.store.get_day(20260808), {h.id: 1})
        self.assertEqual(self.store.toggle(h.id, 20260808), 0)
        # Cleared, not stored as zero.
        self.assertEqual(self.store.get_day(20260808), {})
        self.assertEqual(self.col.conf["awd_habits_log_2026"], {})

    def test_count_habit_steps_then_wraps(self):
        h = self.add(kind="count", target=3, unit="km")
        self.assertEqual(self.store.toggle(h.id, 20260808), 1)
        self.assertEqual(self.store.toggle(h.id, 20260808), 2)
        self.assertEqual(self.store.toggle(h.id, 20260808), 3)
        self.assertEqual(self.store.toggle(h.id, 20260808), 0)

    def test_value_is_capped_at_the_target(self):
        h = self.add(kind="count", target=3)
        self.assertEqual(self.store.set_value(h.id, 20260808, 99), 3)

    def test_log_is_partitioned_by_year(self):
        h = self.add()
        self.store.toggle(h.id, 20251231)
        self.store.toggle(h.id, 20260101)
        self.assertIn("awd_habits_log_2025", self.col.conf)
        self.assertIn("awd_habits_log_2026", self.col.conf)
        self.assertEqual(self.col.conf["awd_habits_log_2025"], {h.id: {"20251231": 1}})

    def test_stored_day_keys_are_strings_and_read_back_as_ints(self):
        h = self.add()
        self.store.toggle(h.id, 20260808)
        stored = self.col.conf["awd_habits_log_2026"][h.id]
        self.assertEqual(list(stored), ["20260808"])
        fresh = store.HabitStore()
        self.assertEqual(fresh.values(h.id, 20260101, 20261231), {20260808: 1})

    def test_values_spans_years(self):
        h = self.add()
        self.store.toggle(h.id, 20251231)
        self.store.toggle(h.id, 20260101)
        self.assertEqual(self.store.values(h.id, 20251230, 20260102),
                         {20251231: 1, 20260101: 1})
        self.assertEqual([d for d, _ in self.store.range(h.id, 20251230, 20260102)],
                         [20251231, 20260101])

    def test_archive_keeps_the_log(self):
        h = self.add()
        self.store.toggle(h.id, 20260807)
        self.store.archive(h.id)
        self.assertEqual(self.store.habits(), [])
        kept = self.store.habits(include_archived=True)[0]
        self.assertTrue(kept.archived)
        self.assertEqual(kept.archived_at, 20260808)
        self.assertEqual(self.store.value(h.id, 20260807), 1)

    def test_purge_removes_every_year(self):
        h = self.add()
        other = self.add(name="Other")
        self.store.toggle(h.id, 20251231)
        self.store.toggle(h.id, 20260101)
        self.store.toggle(other.id, 20260101)
        self.store.purge(h.id)
        self.assertEqual([x.id for x in self.store.habits()], [other.id])
        self.assertEqual(self.col.conf["awd_habits_log_2025"], {})
        self.assertEqual(self.col.conf["awd_habits_log_2026"], {other.id: {"20260101": 1}})

    def test_reorder_renumbers_and_keeps_unlisted_habits(self):
        a, b, c = self.add(name="A"), self.add(name="B"), self.add(name="C")
        self.store.reorder([c.id, a.id])
        self.assertEqual([h.name for h in self.store.habits()], ["C", "A", "B"])
        self.assertEqual([h.pos for h in self.store.habits()], [0, 1, 2])

    def test_update_rejects_a_change_that_would_break_the_record(self):
        h = self.add()
        self.store.update(h.id, name="")
        self.assertEqual(self.store.get(h.id).name, "Read")

    def test_years_index_is_recorded_for_purge(self):
        h = self.add()
        self.store.toggle(h.id, 20251231)
        self.assertIn(2025, self.col.conf["awd_habits_meta"]["years"])

    def test_a_sync_that_replaces_the_year_survives_the_next_tick(self):
        """What `sync_did_finish -> reset()` is for.

        A sync swaps `awd_habits_log_<year>` for another device's whole copy.
        The cache has no expiry, so without the drop the stale copy stays in
        memory and the next tick writes the entire stale year back over what
        just arrived — a silent loss of every tick the other device made.
        """
        h = self.add()
        self.store.toggle(h.id, 20260807)
        self.store.flush()

        # The other device had also ticked the 1st; sync hands us its blob.
        self.col.conf["awd_habits_log_2026"] = {h.id: {"20260801": 1, "20260807": 1}}
        self.store.reset()

        self.assertEqual(self.store.value(h.id, 20260801), 1)
        self.store.toggle(h.id, 20260808)
        self.store.flush()
        self.assertEqual(
            sorted(self.col.conf["awd_habits_log_2026"][h.id]),
            ["20260801", "20260807", "20260808"],
        )

    def test_reset_drops_pending_writes(self):
        h = self.add()
        self.store._dirty.add(2026)     # simulate a write the timer has not run
        self.store._log(2026).setdefault(h.id, {})[20260808] = 1
        self.store.reset()
        self.assertEqual(self.store.value(h.id, 20260808), 0)

    def test_no_collection_is_survivable(self):
        _aqt.mw.col = None
        empty = store.HabitStore()
        self.assertEqual(empty.habits(), [])
        self.assertEqual(empty.get_day(20260808), {})
        empty.flush()                   # must not raise

    def test_prefs_merge_over_defaults(self):
        self.assertTrue(self.store.prefs()["hideArchived"])
        self.store.set_pref("reportView", "year")
        self.assertEqual(self.col.conf["awd_habits_prefs"]["reportView"], "year")


# --- report -------------------------------------------------------------------------

class ReportTests(unittest.TestCase):
    WEEK = (20260803, 20260809)   # Monday to Sunday, today is Saturday the 8th
    TODAY = 20260808

    def block(self, habit, values, view="week", first=None, last=None):
        first = self.WEEK[0] if first is None else first
        last = self.WEEK[1] if last is None else last
        return report.habit_block(habit, values, first, last, self.TODAY,
                                  scheduling.MONDAY, view, True)

    def test_period_bounds_per_view(self):
        self.assertEqual(report.period_bounds("week", 20260812), (20260810, 20260816))
        self.assertEqual(report.period_bounds("month", 20260812), (20260801, 20260831))
        self.assertEqual(report.period_bounds("year", 20260812), (20260101, 20261231))
        # Anything unrecognised falls back to the week rather than crashing.
        self.assertEqual(report.period_bounds("junk", 20260812), (20260810, 20260816))

    def test_shift_period_per_view(self):
        self.assertEqual(report.shift_period("week", 20260812, 1), 20260817)
        self.assertEqual(report.shift_period("week", 20260812, -1), 20260803)
        self.assertEqual(report.shift_period("month", 20260812, 1), 20260912)
        self.assertEqual(report.shift_period("year", 20260812, -1), 20250812)

    def test_levels_spell_out_the_period(self):
        h = weekdays([1, 2, 3, 4, 5], created=20260804)
        values = {20260804: 1, 20260806: 1}
        # Mon: before it existed, Tue: done, Wed: missed, Thu: done,
        # Fri: missed, Sat/Sun: not scheduled — and Sunday is still ahead.
        self.assertEqual(self.block(h, values)["levels"], "x202 0-f".replace(" ", ""))

    def test_levels_mark_a_partial_count(self):
        h = daily(kind="count", target=10, created=20260803)
        block = self.block(h, {20260803: 10, 20260804: 4})
        self.assertEqual(block["levels"], "2100 00f".replace(" ", ""))

    def test_level_string_always_covers_the_whole_period(self):
        block = self.block(daily(created=20260101), {},
                           view="year", first=20260101, last=20261231)
        self.assertEqual(len(block["levels"]), 365)

    def test_week_view_scores_a_weekly_habit_on_its_open_week(self):
        # completion() keeps the running week out of the denominator, which
        # would leave the row reading 0% next to "3/3 this week".
        h = weekly(3, created=20260601)
        values = {20260803: 1, 20260805: 1, 20260807: 1}
        week = self.block(h, values, view="week")
        self.assertEqual((week["done"], week["due"]), (3, 3))
        self.assertEqual(week["rate"], 1.0)
        self.assertEqual(week["inProgress"], {"done": 3, "target": 3})
        # A month still excludes it: there the running week is one of several,
        # and the denominator is the weeks that have finished. August overlaps
        # the week of 27 July, which is the only one owed.
        month = self.block(h, values, view="month", first=20260801, last=20260831)
        self.assertEqual((month["done"], month["due"]), (0, 3))
        self.assertEqual(month["inProgress"], {"done": 3, "target": 3})

    def test_perfect_days_need_every_scheduled_habit(self):
        blocks = [
            {"weekly": False, "levels": "222"},
            {"weekly": False, "levels": "22-"},
            {"weekly": False, "levels": "202"},
        ]
        # Day 0: all three done. Day 1: the third missed. Day 2: two done,
        # one not scheduled — still a full day.
        self.assertEqual(report.perfect_days(blocks, 20260803, 20260805, self.TODAY), 2)

    def test_weekly_habits_cannot_block_a_perfect_day(self):
        blocks = [
            {"weekly": False, "levels": "22"},
            {"weekly": True, "levels": "00"},
        ]
        self.assertEqual(report.perfect_days(blocks, 20260803, 20260804, self.TODAY), 2)

    def test_perfect_days_with_only_weekly_habits_is_zero(self):
        blocks = [{"weekly": True, "levels": "22"}]
        self.assertEqual(report.perfect_days(blocks, 20260803, 20260804, self.TODAY), 0)

    def test_summary_streak_never_mixes_days_and_weeks(self):
        blocks = [
            {"weekly": False, "levels": "2", "done": 1, "due": 1,
             "daysDone": 1, "streak": 3, "longest": 5},
            {"weekly": True, "levels": "2", "done": 3, "due": 3,
             "daysDone": 3, "streak": 10, "longest": 12},
        ]
        summary = report.summarise(blocks, 20260803, 20260803, self.TODAY)
        # The weekly habit's 12 weeks must not be reported as 12 days.
        self.assertEqual((summary["longest"], summary["streakUnit"]), (5, "days"))
        self.assertEqual(summary["done"], 4)
        self.assertEqual(summary["due"], 4)

    def test_summary_falls_back_to_weeks_when_nothing_else_is_there(self):
        blocks = [{"weekly": True, "levels": "2", "done": 3, "due": 3,
                   "daysDone": 3, "streak": 10, "longest": 12}]
        summary = report.summarise(blocks, 20260803, 20260803, self.TODAY)
        self.assertEqual((summary["longest"], summary["streakUnit"]), (12, "weeks"))

    def test_summary_of_nothing_is_zero_not_a_crash(self):
        summary = report.summarise([], 20260803, 20260809, self.TODAY)
        self.assertEqual(summary["rate"], 0.0)
        self.assertEqual(summary["longest"], 0)

    def test_archived_habits_only_appear_in_the_periods_they_lived_in(self):
        h = daily(created=20260601, archived=True, archived_at=20260705)
        self.assertTrue(report.in_period(h, 20260701))
        self.assertFalse(report.in_period(h, 20260801))
        self.assertTrue(report.in_period(daily(), 20260801))


# --- the two layers agreeing -------------------------------------------------------

class ConsistencyTests(unittest.TestCase):
    """A 100% month next to a broken streak is the bug this guards against."""

    def test_full_month_means_a_full_streak(self):
        h = daily(created=20260801)
        values = {day: 1 for day in scheduling.iter_days(20260801, 20260808)}
        rate = stats.completion(h, values, 20260801, 20260831, today=20260808)
        streak = stats.streaks(h, values, today=20260808)
        self.assertEqual(rate["rate"], 1.0)
        self.assertEqual(streak["current"], rate["due"])

    def test_weekly_full_rate_means_a_full_week_streak(self):
        h = weekly(2, created=20260727)
        values = {20260727: 1, 20260728: 1, 20260803: 1, 20260804: 1}
        rate = stats.completion(h, values, 20260727, 20260809,
                                today=20260809, first_day=scheduling.MONDAY)
        streak = stats.streaks(h, values, today=20260809,
                               first_day=scheduling.MONDAY)
        self.assertEqual(rate["rate"], 1.0)
        self.assertEqual(streak["current"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
