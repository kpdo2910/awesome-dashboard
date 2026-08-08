"""Streaks, completion rates and aggregation over a habit's log.

No `aqt` import, and `today` always arrives as an argument — the whole module
is exercised by `tools/test_habits.py` without Anki.

Every function takes `values`: `{day_int: value}` for **one** habit, as handed
out by `HabitStore.values()`. The log is sparse, so a missing key means "not
done", never zero.

Streaks and rates both run through `scheduling.is_due`, and both build on the
same list of evaluable units (`_units`) — that is what keeps "4 week streak"
and "100% this month" from contradicting each other.
"""

from . import scheduling
from .scheduling import (
    MONDAY,
    is_active,
    is_due,
    is_weekly,
    iso_weekday,
    iter_days,
    shift,
    week_start,
    weekly_target,
    weeks_in,
)


# --- single days ----------------------------------------------------------------

def value_on(values: dict, day: int) -> int:
    try:
        return int(values.get(day, 0) or 0)
    except (TypeError, ValueError):
        return 0


def is_done(habit, values: dict, day: int) -> bool:
    return habit.is_complete(value_on(values, day))


def day_ratio(habit, values: dict, day: int) -> float:
    """How far through the day's target the habit got, 0…1."""
    if habit.target <= 0:
        return 0.0
    return min(1.0, value_on(values, day) / habit.target)


# --- the shared unit list -----------------------------------------------------

def _floor_day(habit, values: dict, ref: int) -> int:
    """Earliest day worth walking back to.

    Records written before this add-on tracked `created` have 0, which would
    otherwise send the backwards walk into the year zero; the oldest logged day
    is the honest floor in that case.
    """
    if habit.created:
        return habit.created
    if values:
        return min(values)
    return ref


def _day_units(habit, values: dict, ref: int) -> list:
    """[bool] — one entry per due day from the floor up to `ref`, oldest first.

    A day the habit is not scheduled for is not an entry at all: skipping
    Saturday on a weekdays-only habit must neither count nor break.
    """
    floor = _floor_day(habit, values, ref)
    if floor > ref:
        return []
    return [
        is_done(habit, values, day)
        for day in iter_days(floor, ref)
        if is_active(habit, day) and is_due(habit, day)
    ]


def week_count(habit, values: dict, start: int) -> int:
    """Repetitions done in the week beginning `start` — days that hit target."""
    return sum(1 for day in iter_days(start, shift(start, 6))
               if is_done(habit, values, day))


def countable_weeks(habit, first: int, last: int, first_day: int = MONDAY) -> list:
    """Week starts in the window that the habit can fairly be scored on.

    Shared by the streak and the rate. A week is skipped when the habit was not
    live for the whole of it: added on Friday, it cannot owe three sessions for
    that week, and neither the streak nor the percentage should say it does.
    """
    weeks = []
    for start, end in weeks_in(first, last, first_day):
        if habit.created and habit.created > start:
            continue
        if habit.archived and habit.archived_at and habit.archived_at < end:
            continue
        weeks.append(start)
    return weeks


def _week_units(habit, values: dict, ref: int, first_day: int) -> list:
    floor = _floor_day(habit, values, ref)
    if floor > ref:
        return []
    target = weekly_target(habit)
    return [
        week_count(habit, values, start) >= target
        for start in countable_weeks(habit, floor, ref, first_day)
    ]


def _units(habit, values: dict, ref: int, first_day: int = MONDAY) -> list:
    return (
        _week_units(habit, values, ref, first_day)
        if is_weekly(habit)
        else _day_units(habit, values, ref)
    )


def streaks(habit, values: dict, today: int, first_day: int = MONDAY) -> dict:
    """{"current": n, "longest": n} in days, or in weeks for a weekly habit.

    The open unit — today, or this week — is dropped when it is not finished
    yet: an unticked habit at 9am has not broken anything. That single rule is
    also what keeps `current` from ever exceeding `longest`.
    """
    ref = today
    if habit.archived and habit.archived_at:
        ref = min(today, habit.archived_at)
    units = _units(habit, values, ref, first_day)
    if units and not units[-1]:
        units = units[:-1]

    current = 0
    for done in reversed(units):
        if not done:
            break
        current += 1

    longest = run = 0
    for done in units:
        run = run + 1 if done else 0
        longest = max(longest, run)
    return {"current": current, "longest": longest, "weekly": is_weekly(habit)}


# --- windows ---------------------------------------------------------------------

def completion(habit, values: dict, first: int, last: int, today: int,
               first_day: int = MONDAY) -> dict:
    """Done / due over a window, plus the rate as 0…1.

    Weekly habits are counted in weeks, and the week still running is reported
    separately instead of being scored as a failure. The week the habit was
    created in is skipped unless the habit existed for all of it — a habit added
    on Friday cannot owe three sessions for that week.
    """
    if is_weekly(habit):
        return _weekly_completion(habit, values, first, last, today, first_day)

    days = scheduling.scheduled_days(habit, first, last, today)
    done = sum(1 for day in days if is_done(habit, values, day))
    total = len(days)
    return {
        "done": done,
        "due": total,
        "rate": (done / total) if total else 0.0,
        "weekly": False,
        "in_progress": None,
    }


def _weekly_completion(habit, values: dict, first: int, last: int, today: int,
                       first_day: int) -> dict:
    target = weekly_target(habit)
    current_week = week_start(today, first_day)
    done = total = 0
    in_progress = None
    for start in countable_weeks(habit, first, min(last, today), first_day):
        count = min(week_count(habit, values, start), target)
        if start == current_week:
            in_progress = {"done": count, "target": target}
            continue
        done += count
        total += target
    return {
        "done": done,
        "due": total,
        "rate": (done / total) if total else 0.0,
        "weekly": True,
        "in_progress": in_progress,
    }


def totals(habit, values: dict, first: int, last: int, today: int) -> dict:
    """Raw sums over a window: days completed and the counted total."""
    last = min(last, today)
    days_done = 0
    amount = 0
    if first <= last:
        for day in iter_days(first, last):
            value = value_on(values, day)
            if not value:
                continue
            amount += value
            if habit.is_complete(value):
                days_done += 1
    return {"days_done": days_done, "amount": amount}


def weekday_rates(habit, values: dict, first: int, last: int, today: int) -> list:
    """Completion rate per ISO weekday, index 0 = Monday.

    `None` where the habit is never scheduled on that weekday, so the report can
    tell "never due" apart from "always missed".
    """
    done = [0] * 7
    due = [0] * 7
    for day in scheduling.scheduled_days(habit, first, last, today):
        index = iso_weekday(day) - 1
        due[index] += 1
        if is_done(habit, values, day):
            done[index] += 1
    return [
        (done[i] / due[i]) if due[i] else None
        for i in range(7)
    ]


# --- across all habits ------------------------------------------------------------

def day_summary(habits: list, day_values: dict, day: int, week_done=None) -> dict:
    """{"done": n, "due": n} for one day across the habits due on it.

    Weekly habits count towards "due" every day — each day is a chance to make
    one of the week's repetitions, and a total that shrank whenever one was
    skipped would never be comparable with yesterday's. They count as *done*
    once the week's target is met, though: "three times a week", already done
    three times, is not an outstanding task on Friday, and leaving it in the
    numerator's way would mean the counter could never reach its own total.

    `week_done` is `{habit_id: repetitions so far this week}`; without it the
    weekly habits are judged on today alone.
    """
    week_done = week_done or {}
    done = due = 0
    for habit in habits:
        if not is_active(habit, day) or not is_due(habit, day):
            continue
        due += 1
        if habit.is_complete(int(day_values.get(habit.id, 0) or 0)):
            done += 1
        elif is_weekly(habit) and week_done.get(habit.id, 0) >= weekly_target(habit):
            done += 1
    return {"done": done, "due": due}
