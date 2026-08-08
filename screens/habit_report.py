"""Habit report — week, month and year, as an overlay over the dashboard.

Python owns every date and every number; `web/habits/report.js` only draws what
it is handed. Switching tab or period is a `pycmd` round trip rather than a
second implementation of `is_due` in JavaScript — the two would drift, and the
report exists precisely to be trusted.

**Not a dialog with a webview of its own.** Three separate failures came from
that: the app froze because a non-modal window sat over a modal one and Anki's
`gui_hooks` kept pointing at the destroyed webview, and twice the page came up
blank because the first payload went through `eval`, which waits for a `domDone`
that may never arrive. This renders into the deck browser's *existing* webview,
which is the pattern the onboarding overlay already uses here — no second
`AnkiWebView`, no lifecycle to get wrong, and pushing data into that page is the
mechanism habit ticks have been using all along.

The numbers live in `features/habits/report.py`, which imports no `aqt` and is
covered by `tools/test_habits.py`. What is left here is the overlay's HTML, the
titles and the translated labels.
"""

import html
import json

from aqt import mw

from ..core.translations import month_name, tr, weekday_short
from ..features.habits import report, scheduling
from ..features.habits.store import get_store

VIEWS = report.VIEWS


def _title(view: str, first: int, last: int) -> str:
    if view == "year":
        return str(scheduling.year_of(first))
    if view == "month":
        return f"{month_name(scheduling.to_date(first).month)} {scheduling.year_of(first)}"
    start, end = scheduling.to_date(first), scheduling.to_date(last)
    # "3 – 9 Aug 2026" inside one month, "28 Dec – 3 Jan 2027" across two.
    left = str(start.day) if start.month == end.month \
        else f"{start.day} {month_name(start.month)}"
    return f"{left} – {end.day} {month_name(end.month)} {end.year}"


def payload(view: str, anchor: int, hide_archived: bool) -> dict:
    store = get_store()
    today = store.today()
    first_day = store.first_weekday()
    view = view if view in VIEWS else "week"
    first, last = report.period_bounds(view, anchor, first_day)

    habits = [
        habit for habit in store.habits(include_archived=not hide_archived)
        if report.in_period(habit, first)
    ]
    since = report.history_window(first)
    blocks = [
        report.habit_block(
            habit, store.values(habit.id, since, last),
            first, last, today, first_day, view, view != "year",
        )
        for habit in habits
    ]

    return {
        "view": view,
        "anchor": anchor,
        "first": first,
        "last": last,
        "today": today,
        "firstDay": first_day,
        "title": _title(view, first, last),
        "canNext": last < today,
        "hideArchived": hide_archived,
        "dow": [weekday_short((first_day - 1 + offset) % 7) for offset in range(7)],
        "months": [month_name(m) for m in range(1, 13)],
        "habits": blocks,
        "summary": report.summarise(blocks, first, last, today),
        "i18n": _strings(),
    }


def _strings() -> dict:
    return {
        "week": tr("report_week"),
        "month": tr("report_month"),
        "year": tr("report_year"),
        "today": tr("report_today"),
        "prev": tr("report_prev"),
        "next": tr("report_next"),
        "completion": tr("report_completion"),
        "perfect": tr("report_perfect_days"),
        "ticks": tr("report_ticks"),
        # Two words for the same idea: the tiles are set in caps like the rest
        # of the dashboard's labels, the inline meta line is not.
        "longest": tr("report_longest"),
        "best": tr("longest_streak"),
        "showArchived": tr("habit_show_archived"),
        "archived": tr("habit_archived_tag"),
        "empty": tr("report_empty"),
        "emptyHint": tr("report_empty_hint"),
        "total": tr("report_total"),
        "inProgress": tr("report_in_progress"),
        "days": tr("days_unit"),
        "weeks": tr("weeks_unit"),
        "loading": tr("report_loading"),
        "failed": tr("report_failed"),
    }




# --- the overlay ---------------------------------------------------------------

# Lives in the dashboard's own webview. State is kept here rather than in the
# page, so a period change survives the deck browser re-rendering underneath.
_state = {"view": "", "anchor": 0, "hide_archived": True}


def overlay_html() -> str:
    """The shell, hidden until asked for.

    Appended to the dashboard body *outside* `.awd` on purpose: cards in there
    animate with `transform`, and a transformed ancestor becomes the containing
    block for `position: fixed`, which would trap the overlay inside the card
    grid instead of covering the screen.
    """
    return f"""
    <div class="awd-rep-overlay" id="awd-rep-overlay" hidden>
      <button class="awd-rep-close" title="{html.escape(tr("close"))}"
              onclick="AwdRep.close()">✕</button>
      <div class="awd-rep" id="awd-rep"></div>
    </div>
    """


def _eval(script: str) -> None:
    try:
        mw.deckBrowser.web.eval(script)
    except Exception as e:
        print(f"[Awesome Dashboard] habit report: cannot reach the page: {e}")


def _reset_state() -> None:
    store = get_store()
    view = str(store.prefs().get("reportView", "week"))
    _state["view"] = view if view in VIEWS else "week"
    _state["anchor"] = store.today()
    _state["hide_archived"] = bool(store.prefs().get("hideArchived", True))


def _push(opening: bool) -> None:
    """Send the current period to the page, or the reason it could not be built."""
    try:
        data = payload(_state["view"], _state["anchor"], _state["hide_archived"])
    except Exception as e:
        # Visible, not swallowed: a report that shows nothing is
        # indistinguishable from one that is still loading.
        print(f"[Awesome Dashboard] habit report failed: {e}")
        _eval(f"window.AwdRep && AwdRep.failed({json.dumps(str(e))});")
        return
    call = "open" if opening else "render"
    _eval(f"window.AwdRep && AwdRep.{call}({json.dumps(data)});")


def open_overlay() -> None:
    get_store().flush()
    _reset_state()
    # The spinner goes up first and separately: building a year of history is
    # fast, but "fast" is not "instant", and a blank pane in between is what
    # this whole screen has been getting wrong.
    _eval("window.AwdRep && AwdRep.busy();")
    _push(opening=True)


def command(action: str) -> None:
    store = get_store()
    if action.startswith("view:"):
        view = action[len("view:"):]
        if view not in VIEWS:
            return
        _state["view"] = view
        store.set_pref("reportView", view)
        # The anchor keeps its day, so week -> year lands on the year the week
        # was in rather than jumping back to today.
    elif action.startswith("nav:"):
        try:
            steps = int(action[len("nav:"):])
        except ValueError:
            return
        first_day = store.first_weekday()
        moved = report.shift_period(_state["view"], _state["anchor"], steps, first_day)
        first, _last = report.period_bounds(_state["view"], moved, first_day)
        if first > store.today():
            return  # nothing to report on a period that has not started
        _state["anchor"] = moved
    elif action == "today":
        _state["anchor"] = store.today()
    elif action.startswith("archived:"):
        # "show" / "hide", not a digit: this was `endswith(":0")` assigned
        # straight to `hide_archived`, which inverted it.
        _state["hide_archived"] = action.endswith(":hide")
        store.set_pref("hideArchived", _state["hide_archived"])
    else:
        return
    _push(opening=False)
