"""Habit storage — the only module in this package that touches the collection.

Everything lives in **collection config** (`col.set_config`), not in the add-on
config and not in a database of our own:

* the add-on config is `meta.json`, which Anki merges against `config.json` on
  every update — user data put there eventually disappears;
* a SQLite file in `user_files/` is not inside a `.colpkg` backup, so restoring
  a backup would silently wipe months of habit history;
* a table of our own inside `collection.anki2` is Rust's to manage, and a schema
  change there can force a full sync.

Collection config rides along in backups and in desktop sync, and is already
where `awd_heatmap_scale` and `awd_pomodoro_sessions` live.

Layout, one key per year so a tick only ever re-serialises the current year:

    awd_habits_meta        {"v": 1, "habits": [...], "years": [2025, 2026]}
    awd_habits_log_2026    {habit_id: {"20260808": 1}}
    awd_habits_prefs       {...}

Writes are debounced: `set_config` marks the collection modified and queues the
key for the next sync, so ticking five habits in a row should be one write, not
five. Every exit path flushes — see `install_hooks`.
"""

from . import scheduling
from .models import Habit, empty_meta, load_habits, migrate, new_id

META_KEY = "awd_habits_meta"
PREFS_KEY = "awd_habits_prefs"
LOG_PREFIX = "awd_habits_log_"

# Long enough that a burst of taps collapses into one write, short enough that
# no realistic click-then-quit beats it — and every exit path flushes anyway.
WRITE_DELAY_MS = 400

DEFAULT_PREFS = {
    "hideArchived": True,
    "reportView": "week",
}


def _log_key(year: int) -> str:
    return f"{LOG_PREFIX}{int(year)}"


class HabitStore:
    """Facade over the config blobs. The UI must not read config directly.

    Only the current year is kept in memory as a rule; a report reaching into
    2023 loads that year on demand and it then stays cached until the profile
    closes. Twenty habits over five years is about 4 MB parsed, next to the
    300 MB Anki already occupies, so nothing here is lazy for memory's sake —
    it is lazy so that opening the dashboard does not parse a decade of JSON.
    """

    def __init__(self):
        self._meta = None
        self._logs = {}
        self._dirty = set()   # "meta", "prefs", or an int year
        self._prefs = None
        self._timer = None

    # --- collection access ---

    def _col(self):
        from aqt import mw

        return mw.col

    def _read(self, key: str, default):
        col = self._col()
        if col is None:
            return default
        try:
            value = col.get_config(key, None)
        except Exception as e:
            print(f"[Awesome Dashboard] habits: cannot read {key}: {e}")
            return default
        return value if isinstance(value, type(default)) else default

    def _write(self, key: str, value) -> None:
        col = self._col()
        if col is None:
            return
        try:
            # `undoable` defaults to False, which is what we want: a habit tick
            # has nothing to do with the review queue, and letting it into the
            # undo stack means Ctrl+Z after answering a card silently unticks
            # a habit instead of undoing the answer.
            col.set_config(key, value)
        except Exception as e:
            print(f"[Awesome Dashboard] habits: cannot write {key}: {e}")

    def today(self) -> int:
        return scheduling.anki_today(self._col())

    def first_weekday(self) -> int:
        return scheduling.first_weekday(self._col())

    # --- meta ---

    def _meta_blob(self) -> dict:
        if self._meta is None:
            self._meta = migrate(self._read(META_KEY, {}) or empty_meta())
        return self._meta

    def habits(self, include_archived: bool = False) -> list:
        habits = load_habits(self._meta_blob())
        if include_archived:
            return habits
        return [h for h in habits if not h.archived]

    def get(self, habit_id: str):
        for habit in self.habits(include_archived=True):
            if habit.id == habit_id:
                return habit
        return None

    def _store_habits(self, habits: list) -> None:
        meta = self._meta_blob()
        meta["habits"] = [h.to_dict() for h in habits]
        self._touch("meta")

    def add(self, habit: Habit) -> Habit:
        habits = self.habits(include_archived=True)
        if not habit.id:
            habit.id = new_id()
        if not habit.created:
            habit.created = self.today()
        habit.pos = max((h.pos for h in habits), default=-1) + 1
        habits.append(habit)
        self._store_habits(habits)
        return habit

    def update(self, habit_id: str, **fields) -> None:
        habits = self.habits(include_archived=True)
        for index, habit in enumerate(habits):
            if habit.id != habit_id:
                continue
            raw = habit.to_dict()
            raw.update(fields)
            replaced = Habit.from_dict(raw)
            if replaced is None:
                return
            habits[index] = replaced
            self._store_habits(habits)
            return

    def replace(self, habit: Habit) -> None:
        """Write a habit object back whole, keeping its position."""
        self.update(habit.id, **habit.to_dict())

    def archive(self, habit_id: str) -> None:
        """Retire a habit but keep its log — the default for "delete".

        Dropping the rows would punch a hole in every past report, and the
        report labels archived habits rather than hiding them.
        """
        self.update(habit_id, archived=True, archived_at=self.today())

    def unarchive(self, habit_id: str) -> None:
        self.update(habit_id, archived=False, archived_at=None)

    def purge(self, habit_id: str) -> None:
        """Delete the habit and every entry it ever had, in every year."""
        habits = [h for h in self.habits(include_archived=True) if h.id != habit_id]
        self._store_habits(habits)
        for year in self._known_years():
            log = self._log(year)
            if habit_id in log:
                del log[habit_id]
                self._touch(year)

    def reorder(self, ordered_ids: list) -> None:
        rank = {habit_id: index for index, habit_id in enumerate(ordered_ids)}
        habits = self.habits(include_archived=True)
        # Ids the caller did not mention keep their relative order behind the
        # ones it did, so a partial list can never scramble the rest.
        habits.sort(key=lambda h: (rank.get(h.id, len(rank) + h.pos), h.pos))
        for index, habit in enumerate(habits):
            habit.pos = index
        self._store_habits(habits)

    # --- log ---

    def _known_years(self) -> list:
        """Years that may hold entries: the index in meta, widened to cover
        everything from the oldest habit to today in case the index was lost."""
        meta = self._meta_blob()
        years = set(meta.get("years") or [])
        years.update(self._logs)
        today_year = scheduling.year_of(self.today())
        created = [h.created for h in self.habits(include_archived=True) if h.created]
        if created:
            years.update(range(scheduling.year_of(min(created)), today_year + 1))
        years.add(today_year)
        return sorted(years)

    def _log(self, year: int) -> dict:
        year = int(year)
        if year not in self._logs:
            raw = self._read(_log_key(year), {})
            log = {}
            for habit_id, days in (raw or {}).items():
                if not isinstance(days, dict):
                    continue
                entries = {}
                for day, value in days.items():
                    try:
                        day_int, amount = int(day), int(value)
                    except (TypeError, ValueError):
                        continue
                    if amount:
                        entries[day_int] = amount
                log[str(habit_id)] = entries
            self._logs[year] = log
        return self._logs[year]

    def _entries(self, habit_id: str, year: int) -> dict:
        return self._log(year).setdefault(habit_id, {})

    def get_day(self, day: int) -> dict:
        """{habit_id: value} for one day. Absent habits simply did not do it."""
        log = self._log(scheduling.year_of(day))
        return {
            habit_id: entries[day]
            for habit_id, entries in log.items()
            if day in entries
        }

    def set_value(self, habit_id: str, day: int, value: int) -> int:
        """Write one day's value, returning what was actually stored.

        Zero deletes the key rather than storing it. The size estimate this
        whole design rests on assumes a sparse log; writing a zero for every
        habit on every day would make it dense and roughly triple it.
        """
        day = int(day)
        year = scheduling.year_of(day)
        entries = self._entries(habit_id, year)
        habit = self.get(habit_id)
        ceiling = max(1, habit.target) if habit else 1
        # Cap a count at its target: the bar is a fraction of the target, and a
        # stray double-tap should not report 400% of a day.
        value = max(0, min(int(value or 0), ceiling))
        if value:
            entries[day] = value
        else:
            entries.pop(day, None)
        self._touch(year)
        return value

    def toggle(self, habit_id: str, day: int) -> int:
        """One tap: finish a binary habit, or add one step to a count habit.

        A count habit that is already at its target wraps back to zero, so the
        same control both fills and clears it.
        """
        habit = self.get(habit_id)
        if habit is None:
            return 0
        current = self.value(habit_id, day)
        if not habit.is_count:
            return self.set_value(habit_id, day, 0 if current else 1)
        if current >= habit.target:
            return self.set_value(habit_id, day, 0)
        return self.set_value(habit_id, day, current + habit.step())

    def value(self, habit_id: str, day: int) -> int:
        return self._log(scheduling.year_of(day)).get(habit_id, {}).get(int(day), 0)

    def values(self, habit_id: str, from_day: int, to_day: int) -> dict:
        """{day: value} for one habit over a window, loading the years it spans."""
        out = {}
        for year in range(scheduling.year_of(from_day), scheduling.year_of(to_day) + 1):
            for day, value in self._log(year).get(habit_id, {}).items():
                if from_day <= day <= to_day:
                    out[day] = value
        return out

    def range(self, habit_id: str, from_day: int, to_day: int):
        """(day, value) pairs in ascending order — the iterator form of `values`."""
        entries = self.values(habit_id, from_day, to_day)
        for day in sorted(entries):
            yield day, entries[day]

    # --- prefs ---

    def prefs(self) -> dict:
        if self._prefs is None:
            stored = self._read(PREFS_KEY, {}) or {}
            merged = dict(DEFAULT_PREFS)
            merged.update({k: v for k, v in stored.items() if v is not None})
            self._prefs = merged
        return self._prefs

    def set_pref(self, key: str, value) -> None:
        self.prefs()[key] = value
        self._touch("prefs")

    # --- write scheduling ---

    def _touch(self, what) -> None:
        self._dirty.add(what)
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        try:
            from aqt.qt import QTimer
        except Exception:
            self.flush()
            return
        if self._timer is None:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.flush)
        # start() on a running single-shot timer restarts it, which is exactly
        # the debounce: the write happens once the taps stop.
        self._timer.start(WRITE_DELAY_MS)

    def flush(self) -> None:
        """Persist everything pending. Safe to call when nothing is dirty."""
        if self._timer is not None:
            self._timer.stop()
        if not self._dirty or self._col() is None:
            self._dirty.clear()
            return
        pending, self._dirty = self._dirty, set()

        years = sorted(y for y in pending if isinstance(y, int))
        if years and self._meta is not None:
            # Record which years have a blob so `purge` knows where to look
            # without guessing at key names.
            known = set(self._meta.get("years") or [])
            if not known.issuperset(years):
                self._meta["years"] = sorted(known.union(years))
                pending.add("meta")

        for year in years:
            log = {
                habit_id: {str(day): value for day, value in sorted(entries.items())}
                for habit_id, entries in self._logs.get(year, {}).items()
                if entries
            }
            self._write(_log_key(year), log)
        if "meta" in pending and self._meta is not None:
            self._write(META_KEY, self._meta)
        if "prefs" in pending and self._prefs is not None:
            self._write(PREFS_KEY, self._prefs)

    def reset(self) -> None:
        """Drop every cache *without* writing.

        Only correct once the pending writes are gone or deliberately abandoned:
        flushing here would push one profile's ticks into whichever collection
        happens to be open.
        """
        if self._timer is not None:
            self._timer.stop()
        self._dirty.clear()
        self._meta = None
        self._prefs = None
        self._logs.clear()

    def invalidate(self) -> None:
        """Persist what is pending, then drop every cache."""
        self.flush()
        self.reset()


_store = None


def get_store() -> HabitStore:
    global _store
    if _store is None:
        _store = HabitStore()
    return _store


def flush() -> None:
    if _store is not None:
        _store.flush()


def invalidate() -> None:
    if _store is not None:
        _store.invalidate()


def reset() -> None:
    if _store is not None:
        _store.reset()


def install_hooks() -> None:
    """Keep the cache and the collection honest with each other.

    `mw.col` is `None` before a profile opens, so nothing here may run at import
    time.

    * `profile_will_close` — flush, then drop. Closing without flushing loses
      the last few ticks.
    * `sync_will_start` — flush, so a tick made seconds earlier is part of what
      goes up. Anki fires this for the sync on close as well as the button.
    * `sync_did_finish` — **drop, do not flush.** A sync can replace
      `awd_habits_log_<year>` wholesale with another device's copy; this cache
      has no expiry, so without this the stale copy stays in memory, the
      dashboard keeps drawing it, and the next tick writes the whole stale year
      back over what just arrived. Dropping instead of flushing costs at most a
      tick made during the sync itself, which beats losing a year of them. Anki
      calls `mw.reset()` straight after this hook, so the screen redraws from
      the collection.
    * `profile_did_open` — drop. Anything still pending belongs to a collection
      that is no longer open, and writing it would file one profile's habits
      under another's.
    """
    from aqt import gui_hooks

    # Hooks pass no arguments today; swallowing any keeps a signature change
    # from taking the feature down with it.
    def on_close(*_args):
        invalidate()

    def on_sync_start(*_args):
        flush()

    def on_drop(*_args):
        reset()

    for name, handler in (
        ("profile_will_close", on_close),
        ("sync_will_start", on_sync_start),
        ("sync_did_finish", on_drop),
        ("profile_did_open", on_drop),
    ):
        hook = getattr(gui_hooks, name, None)
        if hook is None:
            print(f"[Awesome Dashboard] habits: no gui_hooks.{name} on this Anki")
            continue
        hook.append(handler)
