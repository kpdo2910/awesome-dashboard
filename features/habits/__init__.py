"""Habit tracker — define habits, tick them off for today, review the history.

    models.py      the Habit record and its schedule, plain data
    scheduling.py  calendar arithmetic and "is this habit due today"
    stats.py       streaks, completion rates, aggregation
    store.py       collection-config storage, cache and debounced writes

`models`, `scheduling` and `stats` never import `aqt`, so the whole logic layer
runs headless under `tools/test_habits.py`. Only `store` touches the collection.
"""

from .store import get_store  # noqa: F401
