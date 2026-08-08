"""What the week / month / year report is made of — no `aqt`, no `mw`.

`screens/habit_report.py` loads the history and adds the titles and translated
labels; everything with a rule in it lives here so `tools/test_habits.py` can
hold it to account. Three separate wrong numbers were shipped and caught by eye
before this module existed.

A period leaves here as one character per day:

    2 done   1 partial   0 due, missed   - not scheduled
    f future   x outside the habit's life

A year of twenty habits is then a few kilobytes rather than seven thousand
JSON objects, and the string is the single source the grid, the rate and the
full-day count are all read from — they cannot disagree with what is on screen.
"""

from . import scheduling, stats
from .scheduling import MONDAY

VIEWS = ("week", "month", "year")

# Enough history behind the window for a streak that started before it.
STREAK_WINDOW = 730

LEVEL_FUTURE = "f"
LEVEL_INACTIVE = "x"
LEVEL_OFF = "-"
LEVEL_DUE = "0"
LEVEL_PARTIAL = "1"
LEVEL_DONE = "2"
SCORED = (LEVEL_DUE, LEVEL_PARTIAL, LEVEL_DONE)


def period_bounds(view: str, anchor: int, first_day: int = MONDAY) -> tuple:
    if view == "month":
        return scheduling.month_bounds(anchor)
    if view == "year":
        return scheduling.year_bounds(anchor)
    return scheduling.week_bounds(anchor, first_day)


def shift_period(view: str, anchor: int, steps: int, first_day: int = MONDAY) -> int:
    if view == "month":
        return scheduling.add_months(anchor, steps)
    if view == "year":
        return scheduling.add_months(anchor, 12 * steps)
    return scheduling.shift(scheduling.week_start(anchor, first_day), 7 * steps)


def history_window(first: int) -> int:
    """How far back the store has to be read for the streaks in this period."""
    return scheduling.shift(first, -STREAK_WINDOW)


def levels(habit, values: dict, first: int, last: int, today: int) -> str:
    out = []
    for day in scheduling.iter_days(first, last):
        if day > today:
            out.append(LEVEL_FUTURE)
        elif not scheduling.is_active(habit, day):
            out.append(LEVEL_INACTIVE)
        elif not scheduling.is_due(habit, day):
            out.append(LEVEL_OFF)
        else:
            value = stats.value_on(values, day)
            out.append(
                LEVEL_DONE if habit.is_complete(value)
                else (LEVEL_PARTIAL if value else LEVEL_DUE)
            )
    return "".join(out)


def habit_block(habit, history: dict, first: int, last: int, today: int,
                first_day: int, view: str, with_values: bool) -> dict:
    """One habit's row: its level string, its rate, its streaks, its totals."""
    streak = stats.streaks(habit, history, today, first_day)
    rate = stats.completion(habit, history, first, last, today, first_day)
    total = stats.totals(habit, history, first, last, today)

    if view == "week" and rate["in_progress"] and not rate["due"]:
        # A weekly habit's only week inside a week-long window is the one still
        # running, so `completion` leaves it out of the denominator — and the
        # row would then read 0% right next to "3/3 this week". Here the period
        # *is* the scoring unit, so score it directly. The marker stays, so the
        # row can still say the week is not over.
        rate = dict(
            rate,
            done=rate["in_progress"]["done"],
            due=rate["in_progress"]["target"],
        )
        rate["rate"] = rate["done"] / rate["due"] if rate["due"] else 0.0

    block = {
        "id": habit.id,
        "name": habit.name,
        "icon": habit.icon,
        "color": habit.color,
        "count": habit.is_count,
        "target": habit.target,
        "unit": habit.unit,
        "weekly": streak["weekly"],
        "archived": habit.archived,
        "levels": levels(habit, history, first, last, today),
        "done": rate["done"],
        "due": rate["due"],
        "rate": rate["rate"],
        "inProgress": rate["in_progress"],
        "streak": streak["current"],
        "longest": streak["longest"],
        "daysDone": total["days_done"],
        "amount": total["amount"],
    }
    if with_values:
        # Only the week and month views put a number in a tooltip; a year of
        # them is weight the strip cannot use.
        block["values"] = {
            str(day): value
            for day, value in history.items()
            if first <= day <= last
        }
    return block


def perfect_days(blocks: list, first: int, last: int, today: int) -> int:
    """Days where every habit scheduled for that day came in complete.

    Read off the level strings, so it cannot disagree with the grid the user is
    looking at. Weekly habits are left out: they are "due" every day only in
    the sense that any day is a chance to make one of the week's repetitions,
    so counting them would put a full day out of reach for anyone who has one.
    """
    scored = [block for block in blocks if not block["weekly"]]
    if not scored:
        return 0
    span = min(last, today)
    if first > span:
        return 0
    perfect = 0
    for index in range(scheduling.days_between(first, span) + 1):
        due = done = 0
        for block in scored:
            char = block["levels"][index] if index < len(block["levels"]) else LEVEL_OFF
            if char in SCORED:
                due += 1
                if char == LEVEL_DONE:
                    done += 1
        if due and due == done:
            perfect += 1
    return perfect


def summarise(blocks: list, first: int, last: int, today: int) -> dict:
    """The four tiles above the grid."""
    done = sum(block["done"] for block in blocks)
    due = sum(block["due"] for block in blocks)
    # A streak tile must not mix units. Day-scheduled habits win the slot when
    # there are any; a set of nothing but weekly habits gets its own number,
    # labelled in weeks.
    day_based = [block for block in blocks if not block["weekly"]]
    pool = day_based or blocks
    return {
        "rate": (done / due) if due else 0.0,
        "done": done,
        "due": due,
        "perfect": perfect_days(blocks, first, last, today),
        "ticks": sum(block["daysDone"] for block in blocks),
        "streak": max((block["streak"] for block in pool), default=0),
        "longest": max((block["longest"] for block in pool), default=0),
        "streakUnit": "days" if day_based or not blocks else "weeks",
    }


def in_period(habit, first: int) -> bool:
    """Whether an archived habit still belongs in this period.

    Outside the stretch it was alive for it would be a row of blanks, so it is
    dropped rather than shown as a habit that did nothing.
    """
    return not habit.archived or (habit.archived_at or 0) >= first
