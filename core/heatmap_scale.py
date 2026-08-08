"""What counts as a busy day, per user and per period.

The heatmap's four shades used to sit on fixed thresholds (10/25/50 reviews),
which only ever suited someone doing around twenty new cards a day. Everyone
else saw either a flat wall of the darkest shade or almost nothing.

The scale is now anchored on a normal day *for this user at that time*, kept as
change points rather than one value per day: a target moves a few times a year,
so a handful of entries covers a decade and a day's colour never shifts once it
is in the past.

    {"2024-01-01": 40, "2024-06-12": 95}   # reviews expected on a normal day

History from before the add-on was installed has no recorded target, so it is
backfilled from the review log itself — the rolling median of what was actually
done. Days from here on record the real workload instead.
"""

import statistics
from datetime import datetime, timedelta

from aqt import mw

SCALE_KEY = "awd_heatmap_scale"

WINDOW = 30        # days of history behind each backfilled point
BLEND = 30         # days over which backfill fades into the live target
DRIFT = 0.2        # movement needed before a new change point is worth storing
FLOOR = 10         # a fresh collection should not start pitch black
RATIO_RANGE = (1.2, 3.0)


def _load() -> dict:
    try:
        value = mw.col.get_config(SCALE_KEY, None)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _save(points: dict) -> None:
    try:
        mw.col.set_config(SCALE_KEY, points)
    except Exception:
        pass


def clear() -> None:
    """Drop the stored scale — the review log it describes is gone."""
    _save({})


def reviews_per_card() -> float:
    """Answers per card over the last month, which is what turns a card target
    into a review target. Learning steps and lapses push this above 1."""
    try:
        cutoff = (mw.col.sched.day_cutoff - 30 * 86400) * 1000
        reviews, cards = mw.col.db.first(
            "SELECT count(), count(DISTINCT cid) FROM revlog"
            " WHERE id > ? AND type IN (0, 1, 2, 3)",
            cutoff,
        ) or (0, 0)
    except Exception:
        return 2.0
    if not cards:
        return 2.0
    low, high = RATIO_RANGE
    return max(low, min(high, reviews / cards))


def _compress(series: list) -> dict:
    """[(day, value), ...] -> only the days where the value really moved."""
    points = {}
    last = None
    for day, value in series:
        value = max(FLOOR, int(round(value)))
        if last is None or abs(value - last) > last * DRIFT:
            points[day] = value
            last = value
    return points


def backfill(calendar: dict, live_target: int) -> dict:
    """Reconstruct the scale for days that predate any recorded target.

    Each day is measured against the median of the *active* days behind it —
    counting rest days would drag the median to zero for anyone who studies a
    few times a week. The tail then fades into today's real target so the join
    between reconstructed and recorded history is a slope, not a step.
    """
    if not calendar:
        return {}
    days = sorted(calendar)
    try:
        start = datetime.strptime(days[0], "%Y-%m-%d").date()
        end = datetime.strptime(days[-1], "%Y-%m-%d").date()
    except ValueError:
        return {}

    series = []
    window = []
    carried = live_target or FLOOR
    day = start
    while day <= end:
        key = day.strftime("%Y-%m-%d")
        count = calendar.get(key, 0)
        if count:
            window.append(count)
        if len(window) > WINDOW:
            window = window[-WINDOW:]
        carried = statistics.median(window) if window else carried
        series.append((key, carried))
        day += timedelta(days=1)

    if live_target:
        # Ramp the last stretch toward the live target, weighted by how close
        # each day is to the join.
        tail = series[-BLEND:]
        for offset, (key, value) in enumerate(tail):
            weight = (offset + 1) / len(tail)
            series[len(series) - len(tail) + offset] = (
                key,
                value * (1 - weight) + live_target * weight,
            )
    return _compress(series)


def record(target: int) -> None:
    """Store today's workload, but only when it has genuinely moved."""
    target = max(FLOOR, int(round(target)))
    points = _load()
    today = datetime.fromtimestamp(mw.col.sched.day_cutoff - 86400).strftime("%Y-%m-%d")
    if points:
        last_day = max(points)
        last = points[last_day]
        if last_day == today:
            points[today] = target
            _save(points)
            return
        if abs(target - last) <= last * DRIFT:
            return
    points[today] = target
    _save(points)


def points_for_web(calendar: dict, live_target: int) -> list:
    """[[day, value], ...] sorted, ready for the heatmap to bisect.

    An empty store means the add-on has never seen this collection before, so
    the reconstruction runs once and is written out.
    """
    points = _load()
    if not points and calendar:
        points = backfill(calendar, live_target)
        if points:
            _save(points)
    return sorted(([day, value] for day, value in points.items()), key=lambda p: p[0])
