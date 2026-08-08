"""Calendar arithmetic and "is this habit due on that day".

No `aqt` import: `anki_today` takes the collection as an argument rather than
reaching for `mw`, so every function here runs under `tools/test_habits.py`
with nothing but the standard library.

`is_due` is deliberately the only answer to "does this day count", shared by
the streak and the completion rate. Two implementations of the same question
drift, and the user then sees a 100% week next to a broken streak with no way
to tell which one is lying.
"""

from datetime import date, datetime, timedelta

from .models import (
    SCHEDULE_DAILY,
    SCHEDULE_TIMES_PER_WEEK,
    SCHEDULE_WEEKDAYS,
)

MONDAY = 1
SUNDAY = 7


# --- day <-> date -------------------------------------------------------------

def to_date(day: int) -> date:
    day = int(day)
    return date(day // 10000, (day // 100) % 100, day % 100)


def from_date(value: date) -> int:
    return value.year * 10000 + value.month * 100 + value.day


def shift(day: int, days: int) -> int:
    return from_date(to_date(day) + timedelta(days=days))


def year_of(day: int) -> int:
    return int(day) // 10000


def iter_days(first: int, last: int):
    """Every day from `first` to `last` inclusive, ascending."""
    cursor = to_date(first)
    end = to_date(last)
    while cursor <= end:
        yield from_date(cursor)
        cursor += timedelta(days=1)


def days_between(first: int, last: int) -> int:
    return (to_date(last) - to_date(first)).days


def iso_weekday(day: int) -> int:
    """1 = Monday … 7 = Sunday, matching the stored `weekdays` schedule."""
    return to_date(day).isoweekday()


# --- today, Anki's definition of it -------------------------------------------

def today_from_cutoff(day_cutoff: int) -> int:
    """The current day given Anki's `day_cutoff` timestamp.

    `day_cutoff` is the moment the *next* Anki day begins, so today is the day
    one rollover earlier. Studying at 2am on the 9th belongs to the 8th, and the
    habit streak has to agree with the review streak sitting next to it on the
    same dashboard.
    """
    return from_date(datetime.fromtimestamp(int(day_cutoff) - 86400).date())


def anki_today(col) -> int:
    """Today as YYYYMMDD, honouring Anki's rollover hour.

    Never `date.today()` — the default rollover is 4am, and a calendar date
    would let a late-night session tick tomorrow's box.
    """
    try:
        return today_from_cutoff(col.sched.day_cutoff)
    except Exception:
        return from_date(date.today())


def first_weekday(col) -> int:
    """Which day the week starts on, as an ISO weekday (1 = Monday).

    Follows Anki's own preference so the report's weeks line up with the graphs
    in Anki's statistics; its key counts from Sunday, JavaScript style. Anything
    unexpected falls back to Monday rather than guessing.
    """
    try:
        raw = col.get_config("firstDayOfWeek", 1)
        value = int(raw)
    except Exception:
        return MONDAY
    if not 0 <= value <= 6:
        return MONDAY
    return SUNDAY if value == 0 else value


# --- period bounds --------------------------------------------------------------

def week_start(day: int, first: int = MONDAY) -> int:
    offset = (iso_weekday(day) - first) % 7
    return shift(day, -offset)


def week_bounds(day: int, first: int = MONDAY) -> tuple:
    start = week_start(day, first)
    return start, shift(start, 6)


def month_bounds(day: int) -> tuple:
    value = to_date(day)
    start = value.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1) - timedelta(days=1)
    return from_date(start), from_date(end)


def year_bounds(day: int) -> tuple:
    year = year_of(day)
    return year * 10000 + 101, year * 10000 + 1231


def add_months(day: int, months: int) -> int:
    """The same day-of-month `months` away, clamped to the month's length."""
    value = to_date(day)
    total = value.year * 12 + (value.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    if month == 12:
        last = 31
    else:
        last = (date(year, month + 1, 1) - timedelta(days=1)).day
    return from_date(date(year, month, min(value.day, last)))


# --- due days --------------------------------------------------------------------

def is_weekly(habit) -> bool:
    """True for schedules measured in weeks rather than days.

    "Three times a week" has no per-day answer: missing Tuesday is not a missed
    day, it is a week that may still finish. Streaks and rates branch on this.
    """
    return habit.schedule_kind == SCHEDULE_TIMES_PER_WEEK


def weekly_target(habit) -> int:
    return max(1, int(habit.schedule.get("n", 3)))


def is_due(habit, day: int) -> bool:
    """Whether `day` is a day this habit is meant to be done.

    Weekly habits return True for every day — each day is a valid chance to do
    one of the week's repetitions. Callers that need a pass/fail must use the
    week helpers in `stats.py`; `is_weekly()` says which is which.
    """
    kind = habit.schedule_kind
    if kind == SCHEDULE_DAILY:
        return True
    if kind == SCHEDULE_WEEKDAYS:
        return iso_weekday(day) in habit.schedule.get("days", [])
    if kind == SCHEDULE_TIMES_PER_WEEK:
        return True
    # Unknown schedule (written by a newer version): treat it as daily rather
    # than hiding the habit from its own report.
    return True


def is_active(habit, day: int) -> bool:
    """Whether the habit existed and was not yet archived on `day`.

    Archived habits stay in the report for the stretch they were live, so a
    finished habit does not retroactively turn its old weeks into failures.
    """
    if habit.created and day < habit.created:
        return False
    if habit.archived and habit.archived_at and day > habit.archived_at:
        return False
    return True


def scheduled_days(habit, first: int, last: int, today: int) -> list:
    """Days in the window that count towards the completion rate.

    Bounded by today (the future cannot be missed), by the habit's creation
    day, and by its archive day.
    """
    if last > today:
        last = today
    if first > last:
        return []
    return [
        day
        for day in iter_days(first, last)
        if is_active(habit, day) and is_due(habit, day)
    ]


def weeks_in(first: int, last: int, first_day: int = MONDAY) -> list:
    """[(week_start, week_end)] covering the window, oldest first.

    Weeks are whole even where the window is not: a rate for "the last 30 days"
    of a weekly habit has to be built from the weeks those days fall in.
    """
    weeks = []
    cursor = week_start(first, first_day)
    end = week_start(last, first_day)
    while cursor <= end:
        weeks.append((cursor, shift(cursor, 6)))
        cursor = shift(cursor, 7)
    return weeks
