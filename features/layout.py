"""Dashboard widgets — which ones, in what order, at what size.

The dashboard is a 15-track grid, so a widget is a fifth, a third, two thirds
or the whole row wide (`xs`, `s`, `m`, `l`) and five stat cards fill a row as
exactly as a heatmap and a Pomodoro do. The layout is one list, stored whole
in `dashboardLayout`; the page edits it client-side and sends it back entire,
so every entry here is validated against WIDGETS before it is kept.

No `aqt` in this module: tools/test_layout.py runs it headless.
"""

SIZES = ("xs", "s", "m", "l")

# id: (allowed sizes, default size). Dict order is the default order.
WIDGETS = {
    "studied": (("xs", "s"), "xs"),
    "time": (("xs", "s"), "xs"),
    "streak": (("xs", "s"), "xs"),
    "retention": (("xs", "s"), "xs"),
    "due": (("xs", "s"), "xs"),
    "habits": (("m", "l"), "l"),
    "heatmap": (("m", "l"), "m"),
    "pomodoro": (("s", "m", "l"), "s"),
    "decks": (("m", "l"), "l"),
}
ORDER = tuple(WIDGETS)
STATS = ("studied", "time", "streak", "retention", "due")

# The switches the layout replaced. A stored config that still carries one and
# has no layout yet is an upgrade, and a block the user had switched off stays
# off.
LEGACY = {
    "showStats": STATS,
    "showHeatmap": ("heatmap",),
    "showPomodoro": ("pomodoro",),
    "showHabits": ("habits",),
}


def _entry(widget_id: str, size: str = None, hidden: bool = False) -> dict:
    allowed, fallback = WIDGETS[widget_id]
    return {
        "id": widget_id,
        "size": size if size in allowed else fallback,
        "hidden": bool(hidden),
    }


def default() -> list:
    return [_entry(widget_id) for widget_id in ORDER]


def normalize(raw) -> list:
    """A complete, valid layout from whatever was stored or sent.

    Unknown ids are dropped, a repeated id keeps its first entry, widgets that
    are missing are appended in default order — so a widget added in a later
    version appears without anyone migrating anything — and a size the widget
    does not offer falls back to its default.
    """
    out = []
    seen = set()
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        widget_id = entry.get("id")
        if widget_id not in WIDGETS or widget_id in seen:
            continue
        seen.add(widget_id)
        out.append(_entry(widget_id, entry.get("size"), entry.get("hidden", False)))
    for widget_id in ORDER:
        if widget_id not in seen:
            out.append(_entry(widget_id))
    return out


def from_config(config: dict) -> list:
    stored = config.get("dashboardLayout")
    if isinstance(stored, list):
        return normalize(stored)
    layout = default()
    for key, ids in LEGACY.items():
        if config.get(key) is False:
            set_hidden(layout, ids, True)
    return layout


def set_hidden(layout: list, ids, hidden: bool) -> list:
    wanted = set(ids)
    for entry in layout:
        if entry["id"] in wanted:
            entry["hidden"] = bool(hidden)
    return layout


def is_hidden(layout: list, widget_id: str) -> bool:
    return any(entry["id"] == widget_id and entry["hidden"] for entry in layout)


def any_visible(layout: list, ids) -> bool:
    wanted = set(ids)
    return any(entry["id"] in wanted and not entry["hidden"] for entry in layout)


def strip_legacy(config: dict) -> None:
    """Drop the replaced switches once a layout exists, so the config editor
    does not show a `showHeatmap: false` next to a heatmap that is on."""
    for key in LEGACY:
        config.pop(key, None)
