"""Grid geometry and the toolbar's options.

**No `aqt` in this module** — `tools/test_preview.py` loads it directly.

Python owns the page size rather than letting the page measure itself: a
payload that arrives already knowing which cards it holds cannot disagree with
the grid that draws them, and the page count is then the same number on both
sides of the bridge.
"""

# Tiles across. Fixed rather than `auto-fill`: the page size has to be a number
# Python can slice with, and asking the page how many columns fitted would put
# a round trip in front of the first render.
COLUMNS = (2, 3, 4, 5, 6)
ROWS = (2, 3, 4, 5, 6)

# Tall through wide, as the reference add-on offers. Written as strings because
# they are config values and a user may read them.
RATIOS = ("3:4", "1:1", "4:3", "16:9")

FONT_MIN, FONT_MAX = 70, 160

FLIP_MODES = ("click", "hover")
SORTS = ("added", "due", "alpha")

DEFAULTS = {
    "columns": 4,
    "rows": 3,
    "ratio": "1:1",
    "font": 100,
    "flip": "click",
    "sort": "added",
}


def _one_of(value, allowed, fallback):
    return value if value in allowed else fallback


def clamp(options: dict) -> dict:
    """Every option forced back into range.

    Config is a JSON file a user can edit by hand, and the grid has to draw
    something for whatever it finds there.
    """
    options = options or {}
    try:
        font = int(options.get("font", DEFAULTS["font"]))
    except (TypeError, ValueError):
        font = DEFAULTS["font"]
    return {
        "columns": _one_of(options.get("columns"), COLUMNS, DEFAULTS["columns"]),
        "rows": _one_of(options.get("rows"), ROWS, DEFAULTS["rows"]),
        "ratio": _one_of(options.get("ratio"), RATIOS, DEFAULTS["ratio"]),
        "font": max(FONT_MIN, min(FONT_MAX, font)),
        "flip": _one_of(options.get("flip"), FLIP_MODES, DEFAULTS["flip"]),
        "sort": _one_of(options.get("sort"), SORTS, DEFAULTS["sort"]),
    }


def per_page(options: dict) -> int:
    options = clamp(options)
    return options["columns"] * options["rows"]


def page_count(total: int, size: int) -> int:
    """At least one page, so an empty deck still has somewhere to say so."""
    if size <= 0:
        return 1
    return max(1, -(-int(total) // int(size)))


def clamp_page(page, pages: int) -> int:
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0
    return max(0, min(int(pages) - 1, page))


def slice_page(items, page: int, size: int) -> list:
    start = clamp_page(page, page_count(len(items), size)) * size
    return list(items[start:start + size])


def page_for_index(index: int, size: int) -> int:
    """Which page a given card sits on.

    Resizing the grid keeps the first tile that was on screen on screen —
    without it, going from twelve per page to eight jumps the reader somewhere
    unrelated and the size control feels like it also scrolled.
    """
    if size <= 0:
        return 0
    return max(0, int(index)) // int(size)


def aspect(ratio: str) -> str:
    """`3:4` as the value CSS `aspect-ratio` wants."""
    width, _, height = _one_of(ratio, RATIOS, DEFAULTS["ratio"]).partition(":")
    return f"{width} / {height}"
