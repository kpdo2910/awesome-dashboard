"""The habit strip on the dashboard — one tap ticks a habit off for today.

Renders a block into the deck browser and hands `web/habits/habits.js` the data
it needs to redraw a chip on its own. Clicks never re-render the page: a full
`deckBrowser.refresh()` per tick would drop the scroll position and flash the
whole screen for a checkbox.

The chip's next value is worked out twice on purpose — optimistically in JS so
the tap feels instant, then authoritatively by `HabitStore.toggle`, whose answer
is pushed back through `AwdHabit.applyValue`. The store is the truth; the JS copy
only has to be right often enough that the correction is invisible.
"""

import html
import json

from aqt import mw

from ..core.translations import tr
from ..features.habits import scheduling, stats
from ..features.habits.store import get_store

# How far back a streak may reach on the dashboard. Two years of chips is
# already more history than the strip can say anything about, and it bounds
# the work done on every render.
STREAK_WINDOW = 730


def _streak_for(store, habit, today: int, first_day: int) -> dict:
    values = store.values(habit.id, scheduling.shift(today, -STREAK_WINDOW), today)
    return stats.streaks(habit, values, today, first_day)


def _week_done(store, habit, today: int, first_day: int) -> int:
    start = scheduling.week_start(today, first_day)
    return stats.week_count(
        habit, store.values(habit.id, start, scheduling.shift(start, 6)), start
    )


def habit_payload(store, habits: list, today: int, first_day: int) -> list:
    """Everything the strip needs about each habit, as plain JSON values."""
    day_values = store.get_day(today)
    payload = []
    for habit in habits:
        value = int(day_values.get(habit.id, 0) or 0)
        streak = _streak_for(store, habit, today, first_day)
        entry = {
            "id": habit.id,
            "name": habit.name,
            "icon": habit.icon,
            "color": habit.color,
            "count": habit.is_count,
            "target": habit.target,
            "unit": habit.unit,
            "step": habit.step(),
            "value": value,
            "due": scheduling.is_due(habit, today),
            "streak": streak["current"],
            "weekly": streak["weekly"],
        }
        if streak["weekly"]:
            entry["weekDone"] = _week_done(store, habit, today, first_day)
            entry["weekTarget"] = scheduling.weekly_target(habit)
        payload.append(entry)
    return payload


def data_for_web() -> dict:
    """`AWD_DATA.habits`, or an empty payload when the block is switched off."""
    store = get_store()
    today = store.today()
    first_day = store.first_weekday()
    habits = store.habits()
    week_done = {
        habit.id: _week_done(store, habit, today, first_day)
        for habit in habits
        if scheduling.is_weekly(habit)
    }
    summary = stats.day_summary(habits, store.get_day(today), today, week_done)
    return {
        "today": today,
        "items": habit_payload(store, habits, today, first_day),
        "done": summary["done"],
        "due": summary["due"],
        "i18n": {
            "done": tr("habit_done_of"),
            "allDone": tr("habit_all_done"),
            "offDay": tr("habit_off_day"),
            "days": tr("days_unit"),
            "weeks": tr("weeks_unit"),
            "thisWeek": tr("habit_week_progress"),
        },
    }


def card_html() -> str:
    """The block itself. The chips are filled in by habits.js from AWD_DATA."""
    from .dashboard import icon

    actions = (
        f'<button class="awd-pill awd-pill-ghost awd-hb-action"'
        f' onclick="pycmd(\'awd:habit:report\')">'
        f'{icon("chart")}<span>{html.escape(tr("habit_report"))}</span></button>'
        f'<button class="awd-pill awd-pill-ghost awd-pill-icon awd-hb-action"'
        f' title="{html.escape(tr("habit_manage"))}"'
        f' onclick="pycmd(\'awd:habit:manage\')">{icon("sliders")}</button>'
    )
    return f"""
    <section class="awd-card awd-hb-card">
      <div class="awd-card-head">
        <span class="awd-chip">{html.escape(tr("habits"))}</span>
        <div class="awd-hb-head">
          <span class="awd-hb-count" id="awd-hb-count"></span>
          {actions}
        </div>
      </div>
      <div class="awd-hb-bar"><i id="awd-hb-fill"></i></div>
      <div class="awd-hb-grid" id="awd-hb-grid"></div>
      <div class="awd-hb-empty" id="awd-hb-empty" hidden>
        <div class="awd-empty-title">{html.escape(tr("habit_empty"))}</div>
        <div class="awd-empty-hint">{html.escape(tr("habit_empty_hint"))}</div>
        <button class="awd-pill awd-pill-accent"
                onclick="pycmd('awd:habit:manage')">
          {icon("plus")}<span>{html.escape(tr("habit_add"))}</span></button>
      </div>
    </section>
    """


# --- bridge commands -----------------------------------------------------------

def _push(habit_id: str, value: int) -> None:
    """Send the stored value back to the page so it can correct itself."""
    try:
        payload = json.dumps({"id": habit_id, "value": value})
        mw.deckBrowser.web.eval(f"window.AwdHabit && AwdHabit.applyValue({payload});")
    except Exception as e:
        print(f"[Awesome Dashboard] habits: cannot push value back: {e}")


def toggle(habit_id: str) -> None:
    store = get_store()
    _push(habit_id, store.toggle(habit_id, store.today()))


def open_manager() -> None:
    from ..ui.habits import open_manager as show

    show(mw)


def open_report() -> None:
    from . import habit_report

    habit_report.open_overlay()
