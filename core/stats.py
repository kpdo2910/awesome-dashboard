"""Collection statistics for the dashboard.

Revlog queries skip type 4 (manual reschedules) and group by local study day,
honouring Anki's rollover hour — the scheduler's own day boundaries.
"""

import time
from datetime import datetime, timedelta

from aqt import mw

_CACHE = {}
_CACHE_TIME = 0.0
_CACHE_TTL = 30  # seconds


def invalidate_cache() -> None:
    global _CACHE, _CACHE_TIME
    _CACHE = {}
    _CACHE_TIME = 0.0


def _rollover_hour() -> int:
    try:
        value = mw.col.get_config("rollover", 4)
    except Exception:
        try:
            value = mw.col.conf.get("rollover", 4)
        except Exception:
            value = 4
    try:
        return int(value)
    except (TypeError, ValueError):
        return 4


def _today_start_seconds() -> int:
    return mw.col.sched.day_cutoff - 86400


def gather() -> dict:
    """All dashboard numbers in one cached bundle."""
    global _CACHE, _CACHE_TIME
    now = time.time()
    if _CACHE and now - _CACHE_TIME < _CACHE_TTL:
        return _CACHE
    if not mw.col:
        return {}

    db = mw.col.db
    today_start = _today_start_seconds()
    today_start_ms = today_start * 1000

    cards_today, secs_today = db.first(
        "SELECT count(), coalesce(sum(time), 0) / 1000 FROM revlog"
        " WHERE id > ? AND type IN (0, 1, 2, 3)",
        today_start_ms,
    ) or (0, 0)
    cards_today = cards_today or 0
    secs_today = secs_today or 0

    month_ago_ms = (today_start - 30 * 86400) * 1000
    total_30, passed_30 = db.first(
        "SELECT count(), coalesce(sum(ease > 1), 0) FROM revlog"
        " WHERE id > ? AND type = 1",
        month_ago_ms,
    ) or (0, 0)
    retention = (passed_30 / total_30 * 100) if total_30 else None

    offset = _rollover_hour() * 3600
    rows = db.all(
        "SELECT strftime('%Y-%m-%d', id / 1000 - ?, 'unixepoch', 'localtime'),"
        " count() FROM revlog WHERE type IN (0, 1, 2, 3)"
        " GROUP BY 1",
        offset,
    )
    calendar = {day: count for day, count in rows}

    today_key = datetime.fromtimestamp(today_start).strftime("%Y-%m-%d")
    streak, longest = _streaks(set(calendar), today_key)

    daily_avg = 0.0
    if calendar:
        first_day = min(calendar)
        try:
            first_date = datetime.strptime(first_day, "%Y-%m-%d").date()
            days_elapsed = max(1, (datetime.fromtimestamp(today_start).date() - first_date).days + 1)
            daily_avg = sum(calendar.values()) / days_elapsed
        except ValueError:
            pass

    _CACHE = {
        "cards_today": cards_today,
        "minutes_today": secs_today / 60,
        "retention": retention,
        "calendar": calendar,
        "today_key": today_key,
        "streak": streak,
        "longest_streak": longest,
        "daily_avg": daily_avg,
    }
    _CACHE_TIME = now
    return _CACHE


def _streaks(review_days: set, today_key: str) -> tuple:
    """(current streak, longest streak). A live streak may still start yesterday."""
    if not review_days:
        return 0, 0

    def prev_day(key: str) -> str:
        d = datetime.strptime(key, "%Y-%m-%d").date() - timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    current = 0
    cursor = today_key
    if cursor not in review_days:
        cursor = prev_day(cursor)
    while cursor in review_days:
        current += 1
        cursor = prev_day(cursor)

    longest = 1
    run = 1
    days = sorted(datetime.strptime(k, "%Y-%m-%d").date() for k in review_days)
    for before, after in zip(days, days[1:]):
        run = run + 1 if (after - before).days == 1 else 1
        longest = max(longest, run)
    return current, max(longest, current)


def due_counts(tree) -> tuple:
    """(new, learn, review) totals from the deck tree's top-level nodes."""
    new = learn = review = 0
    for child in tree.children:
        new += child.new_count
        learn += child.learn_count
        review += child.review_count
    return new, learn, review
