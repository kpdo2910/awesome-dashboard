"""The Habit record — plain data, no Anki imports.

Days are `int` in YYYYMMDD form everywhere in this package. JSON object keys
must be strings, so the log stores `"20260808"` and reads it back with `int()`;
holding the in-memory form as an int keeps every comparison and sort ordinal.

Ids are random, never the name or the list position: renaming a habit or
dragging it up the list must not orphan its log.
"""

import uuid

KIND_BINARY = "binary"
KIND_COUNT = "count"
KINDS = (KIND_BINARY, KIND_COUNT)

SCHEDULE_DAILY = "daily"
SCHEDULE_WEEKDAYS = "weekdays"
SCHEDULE_TIMES_PER_WEEK = "times_per_week"
SCHEDULE_KINDS = (SCHEDULE_DAILY, SCHEDULE_WEEKDAYS, SCHEDULE_TIMES_PER_WEEK)

DEFAULT_ICON = "🎯"
DEFAULT_COLOR = "#34C759"

# Apple system palette, the same family the deck tints use — a habit sitting
# next to a deck row should not look like it came from another app.
PALETTE = [
    "#FF3B30", "#FF9500", "#FFCC00", "#34C759",
    "#00C7BE", "#007AFF", "#5856D6", "#AF52DE",
    "#FF2D55", "#A2845E",
]

# Offered in the editor's icon picker. Any character the user types is kept as
# it is; this is a shortcut, not a whitelist.
ICONS = [
    "🎯", "📖", "💧", "🏃", "🧘", "💪", "🍎", "😴",
    "✍️", "🎧", "🧹", "💊", "🌱", "☀️", "🧠", "🎸",
    "💰", "📵", "🚭", "🥗", "🚴", "🛁", "📷", "🗣️",
]

MAX_TARGET = 100000


def new_id() -> str:
    """Short random id. Eight hex digits is ~4 billion values against a list
    that never runs past a few dozen habits."""
    return f"h_{uuid.uuid4().hex[:8]}"


def normalise_schedule(raw) -> dict:
    """Any stored or user-supplied schedule, coerced into a valid one.

    Falls back to daily rather than raising: a habit with a broken schedule
    should still show up and still be tickable.
    """
    if not isinstance(raw, dict):
        return {"kind": SCHEDULE_DAILY}
    kind = str(raw.get("kind") or SCHEDULE_DAILY)
    if kind == SCHEDULE_WEEKDAYS:
        days = []
        for value in raw.get("days") or []:
            try:
                day = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= day <= 7 and day not in days:
                days.append(day)
        if not days:
            return {"kind": SCHEDULE_DAILY}
        return {"kind": SCHEDULE_WEEKDAYS, "days": sorted(days)}
    if kind == SCHEDULE_TIMES_PER_WEEK:
        try:
            n = int(raw.get("n") or 0)
        except (TypeError, ValueError):
            n = 0
        return {"kind": SCHEDULE_TIMES_PER_WEEK, "n": max(1, min(7, n or 3))}
    return {"kind": SCHEDULE_DAILY}


class Habit:
    """One tracked habit.

    Plain attributes rather than a dataclass so `from_dict` can keep unknown
    keys out and repair partial records in one place — this data survives
    add-on updates, and a record written by a future version must not crash an
    older one.
    """

    __slots__ = (
        "id", "name", "icon", "color", "kind", "target", "unit",
        "schedule", "pos", "archived", "created", "archived_at",
    )

    def __init__(
        self,
        id: str = "",
        name: str = "",
        icon: str = DEFAULT_ICON,
        color: str = DEFAULT_COLOR,
        kind: str = KIND_BINARY,
        target: int = 1,
        unit: str = "",
        schedule=None,
        pos: int = 0,
        archived: bool = False,
        created: int = 0,
        archived_at=None,
    ):
        self.id = id or new_id()
        self.name = name
        self.icon = icon or DEFAULT_ICON
        self.color = color or DEFAULT_COLOR
        self.kind = kind if kind in KINDS else KIND_BINARY
        # A binary habit's target is always 1 — the whole point is that one tick
        # finishes it, and stats compare `value >= target` for both kinds.
        self.target = 1 if self.kind == KIND_BINARY else max(1, min(MAX_TARGET, int(target or 1)))
        self.unit = unit if self.kind == KIND_COUNT else ""
        self.schedule = normalise_schedule(schedule)
        self.pos = int(pos)
        self.archived = bool(archived)
        self.created = int(created or 0)
        self.archived_at = int(archived_at) if archived_at else None

    # --- (de)serialisation ---

    @classmethod
    def from_dict(cls, raw: dict):
        """A stored record, or None if it is too broken to show."""
        if not isinstance(raw, dict):
            return None
        habit_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not habit_id or not name:
            return None
        return cls(
            id=habit_id,
            name=name,
            icon=str(raw.get("icon") or DEFAULT_ICON),
            color=str(raw.get("color") or DEFAULT_COLOR),
            kind=str(raw.get("kind") or KIND_BINARY),
            target=raw.get("target", 1),
            unit=str(raw.get("unit") or ""),
            schedule=raw.get("schedule"),
            pos=_int(raw.get("pos"), 0),
            archived=bool(raw.get("archived")),
            created=_int(raw.get("created"), 0),
            archived_at=raw.get("archived_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "color": self.color,
            "kind": self.kind,
            "target": self.target,
            "unit": self.unit,
            "schedule": dict(self.schedule),
            "pos": self.pos,
            "archived": self.archived,
            "created": self.created,
            "archived_at": self.archived_at,
        }

    def copy(self):
        return Habit.from_dict(self.to_dict())

    # --- helpers ---

    @property
    def is_count(self) -> bool:
        return self.kind == KIND_COUNT

    @property
    def schedule_kind(self) -> str:
        return self.schedule.get("kind", SCHEDULE_DAILY)

    def is_complete(self, value: int) -> bool:
        return int(value or 0) >= self.target

    def step(self) -> int:
        """How much one tap adds for a count habit.

        Big targets (3000 ml of water) would need a hundred taps at 1 apiece, so
        the step scales with the target and lands on a round number.
        """
        if not self.is_count:
            return 1
        for size in (1, 5, 10, 25, 50, 100, 250, 500):
            if self.target <= size * 12:
                return size
        return 1000

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Habit {self.id} {self.name!r} {self.kind} {self.schedule_kind}>"


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# --- collection-level record -------------------------------------------------

META_VERSION = 1


def empty_meta() -> dict:
    return {"v": META_VERSION, "habits": [], "years": []}


def migrate(meta) -> dict:
    """Bring a stored meta blob up to the current version.

    A no-op today, but it runs on every load so the day a field changes shape
    there is already a place for the change to live — and `v` is already being
    written, which is the half that cannot be added retroactively.
    """
    if not isinstance(meta, dict):
        return empty_meta()
    version = _int(meta.get("v"), 0)
    habits = meta.get("habits")
    if not isinstance(habits, list):
        habits = []
    years = [y for y in (meta.get("years") or []) if isinstance(y, int)]
    # (no migrations yet — version 1 is the first shipped shape)
    if version > META_VERSION:
        # Written by a newer add-on. Its version number is preserved so this
        # one cannot silently claim the blob is older than it is; fields this
        # version does not know about are still lost on the next save, which is
        # the price of downgrading.
        return {"v": version, "habits": habits, "years": sorted(set(years))}
    return {"v": META_VERSION, "habits": habits, "years": sorted(set(years))}


def load_habits(meta: dict) -> list:
    """Habit objects from a meta blob, in display order."""
    habits = []
    for raw in meta.get("habits") or []:
        habit = Habit.from_dict(raw)
        if habit is not None:
            habits.append(habit)
    habits.sort(key=lambda h: (h.pos, h.created, h.id))
    return habits
