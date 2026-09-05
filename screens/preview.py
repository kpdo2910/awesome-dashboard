"""Cards preview — the deck's whole card list as a flippable grid.

Drawn into the deck overview's own webview, like the study modes and for the
same reason: a second `AnkiWebView` would have to be parented to something, and
`AnkiWebView.__init__` appends itself to three `gui_hooks` that only `cleanup()`
removes. `Overview._renderPage` delegates here while a grid is open.

Each tile shows what Anki itself renders — `render_output()`, so cloze,
conditional templates and `{{furigana:}}` all come out right — but **not** the
note type's own CSS. That CSS is written for a full screen; in a 180px tile its
font sizes and absolute layouts fall apart, which is exactly why the add-on
this was modelled on had to grow a text-size control. The tile is drawn in the
add-on's palette instead, the same choice the congrats screen makes.

Media needs no work at all: `stdHtml` writes `<base href="{serverURL}">`, and
`aqt/mediasrv.py` falls through to `mw.col.media.dir()` for any path that is
not `_anki/` or `_addons/`. So a relative `<img src="paste-1.jpg">` in this
page resolves to the collection's media folder, which is the one thing the
reference add-on says it cannot do.
"""

import html
import json

from aqt import mw

from ..core import conf
from ..core.translations import tr
from ..features.preview import content, grid

# The add-on config keys this screen reads, and their option names.
OPTION_KEYS = {
    "columns": "cpColumns",
    "rows": "cpRows",
    "ratio": "cpRatio",
    "font": "cpFont",
    "flip": "cpFlip",
    "sort": "cpSort",
}

# Options whose value is a number rather than one of a fixed set.
NUMERIC = ("columns", "rows", "font")

ORDER_BY = {
    # A new card's `due` is a queue position and a review card's is a day
    # number, so the two only sort sensibly once `type` has separated them.
    "due": "c.type asc, c.due asc, c.ord asc",
    "alpha": "n.sfld collate nocase asc, c.ord asc",
    "added": "c.id asc",
}

_active = None


def active() -> bool:
    return _active is not None


def close() -> None:
    global _active
    _active = None


# --- reading the deck ------------------------------------------------------


def _card_ids(deck_id: int, sort: str) -> list:
    """Every card in the deck and its subdecks, in the asked-for order.

    Through `deck_and_child_ids` rather than `find_cards(f'deck:"{name}"')`: a
    deck name inside a search string is a pattern, so a deck called `N5 *`
    would pull in half the collection. `odid` is matched too, or a card on loan
    to a filtered deck vanishes from its home deck's grid.
    """
    try:
        deck_ids = mw.col.decks.deck_and_child_ids(deck_id)
        ids = ",".join(str(int(d)) for d in deck_ids)
        return mw.col.db.list(
            "select c.id from cards c join notes n on n.id = c.nid "
            f"where c.did in ({ids}) or c.odid in ({ids}) "
            f"order by {ORDER_BY.get(sort, ORDER_BY['added'])}"
        )
    except Exception as e:
        print(f"[Awesome Dashboard] preview: cannot read deck {deck_id}: {e}")
        return []


def _filenames(av_tags) -> list:
    """One entry per av tag: a filename, or None where there is nothing to play.

    A TTS tag has no file behind it, and its placeholder is dropped rather than
    drawn as a button that could not do anything.
    """
    return [getattr(tag, "filename", None) for tag in (av_tags or [])]


def _state(card) -> str:
    """The chip on the tile: where this card stands with the scheduler."""
    queue = int(getattr(card, "queue", 0))
    if queue == -1:
        return "suspended"
    if queue in (-2, -3):
        return "buried"
    card_type = int(getattr(card, "type", 0))
    if card_type == 0:
        return "new"
    if card_type in (1, 3):
        return "learn"
    return "due"


def _tile(card_id: int) -> dict:
    try:
        card = mw.col.get_card(card_id)
        out = card.render_output()
    except Exception as e:
        print(f"[Awesome Dashboard] preview: card {card_id} failed: {e}")
        return {}

    front = content.cap(content.clean(
        out.question_text, _filenames(out.question_av_tags)))
    back = content.cap(content.clean(
        content.back_only(out.question_text, out.answer_text),
        _filenames(out.answer_av_tags)))
    return {
        "id": int(card_id),
        "front": front,
        "back": back,
        "frontBlank": content.is_blank(front),
        "backBlank": content.is_blank(back),
        "state": _state(card),
        "flag": int(card.user_flag() or 0),
    }


# --- options ---------------------------------------------------------------


def _options() -> dict:
    config = conf.get()
    return grid.clamp({
        name: config.get(key) for name, key in OPTION_KEYS.items()
    })


def _set_option(name: str, raw: str) -> bool:
    """Persist one toolbar choice. True when the card list has to be rebuilt."""
    if name not in OPTION_KEYS:
        return False
    value = raw
    if name in NUMERIC:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return False
    # Through `clamp` so what is stored is always in range. The font scale is
    # genuinely clamped — 5000 means "as large as it goes" — but the others are
    # a choice from a fixed set, and a value that is not in it is a command
    # that should be ignored rather than one that quietly resets the setting
    # the user had.
    options = _options()
    options[name] = value
    clamped = grid.clamp(options)[name]
    if name != "font" and clamped != value:
        return False
    conf.set_value(OPTION_KEYS[name], clamped)
    return name == "sort"


# --- payload ---------------------------------------------------------------


def _deck_name(deck_id: int) -> str:
    try:
        return str(mw.col.decks.name(deck_id)).rsplit("::", 1)[-1]
    except Exception:
        return ""


def _payload() -> dict:
    options = _options()
    size = grid.per_page(options)
    total = len(_active["ids"])
    pages = grid.page_count(total, size)
    page = grid.clamp_page(_active["page"], pages)
    _active["page"] = page

    tiles = [tile for tile in
             (_tile(cid) for cid in grid.slice_page(_active["ids"], page, size))
             if tile]
    return {
        "deck": _deck_name(_active["deck"]),
        "total": total,
        "page": page,
        "pages": pages,
        "options": options,
        "aspect": grid.aspect(options["ratio"]),
        "columns": list(grid.COLUMNS),
        "rows": list(grid.ROWS),
        "ratios": list(grid.RATIOS),
        "cards": tiles,
        # MathJax is 1.3MB of Anki's own bundle. The page fetches it only when
        # a tile actually carries TeX, so an ordinary deck never pays for it.
        "math": any("\\(" in t["front"] or "\\[" in t["front"]
                    or "\\(" in t["back"] or "\\[" in t["back"] for t in tiles),
    }


def _strings() -> dict:
    return {
        "cp_title": tr("cp_title"),
        "qz_back": tr("qz_back"),
        "cp_page": tr("cp_page"),
        "cp_prev": tr("cp_prev"),
        "cp_next": tr("cp_next"),
        "cp_flip_all": tr("cp_flip_all"),
        "cp_unflip_all": tr("cp_unflip_all"),
        "cp_columns": tr("cp_columns"),
        "cp_rows": tr("cp_rows"),
        "cp_ratio": tr("cp_ratio"),
        "cp_font": tr("cp_font"),
        "cp_flip_mode": tr("cp_flip_mode"),
        "cp_flip_click": tr("cp_flip_click"),
        "cp_flip_hover": tr("cp_flip_hover"),
        "cp_sort": tr("cp_sort"),
        "cp_sort_added": tr("cp_sort_added"),
        "cp_sort_due": tr("cp_sort_due"),
        "cp_sort_alpha": tr("cp_sort_alpha"),
        "cp_cards": tr("cp_cards"),
        "cp_blank": tr("cp_blank"),
        "cp_side_front": tr("cp_side_front"),
        "cp_side_back": tr("cp_side_back"),
        "cp_empty_title": tr("cp_empty_title"),
        "cp_empty_body": tr("cp_empty_body"),
        "cp_state_new": tr("count_new"),
        "cp_state_learn": tr("count_learn"),
        "cp_state_due": tr("count_due"),
        "cp_state_suspended": tr("cp_state_suspended"),
        "cp_state_buried": tr("cp_state_buried"),
    }


# --- drawing ---------------------------------------------------------------


def _redraw() -> None:
    """`_renderPage` rather than `refresh`: refresh runs the deck's counts
    through a `QueryOp` and only draws in its callback, so the grid would
    appear a beat late and behind a query it has no use for."""
    try:
        mw.overview._renderPage()
    except Exception as e:
        print(f"[Awesome Dashboard] preview: cannot draw overview: {e}")


def _send(payload: dict) -> None:
    try:
        blob = json.dumps(payload, ensure_ascii=False)
        mw.overview.web.eval(f"window.AwdCp && AwdCp.apply({blob});")
    except Exception as e:
        print(f"[Awesome Dashboard] preview: send failed: {e}")


def render(overview) -> None:
    """Draw the open grid. Called from `screens/overview.render_page`."""
    blob = json.dumps(_payload(), ensure_ascii=False)
    strings = json.dumps(_strings(), ensure_ascii=False)
    # The first payload rides in the body rather than going through `eval`,
    # which queues until the page posts `domDone` — a screen that has to wait
    # for that to draw anything has "blank" as one of its states.
    body = f"""
    <div class="awd-cp" id="awd-cp"></div>
    <script>
      window.AWD_CP_I18N = {strings};
      window.AWD_CP = {blob};
      if (window.AwdCp) AwdCp.mount();
    </script>
    """
    overview.web.stdHtml(body=body, css=[], js=[], context=overview)
    from . import dashboard

    dashboard.apply_bar_visibility("overview")


def button_html(deck_id: int) -> str:
    """The "Cards preview" entry on the normal overview page."""
    return (
        f'<button class="awd-ov-modes awd-ov-preview"'
        f' onclick="pycmd(\'awd:cp:open:{int(deck_id)}\')">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="3" y="3" width="7.5" height="7.5" rx="1.8"/>'
        '<rect x="13.5" y="3" width="7.5" height="7.5" rx="1.8"/>'
        '<rect x="3" y="13.5" width="7.5" height="7.5" rx="1.8"/>'
        '<rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.8"/></svg>'
        f'<span>{html.escape(tr("cp_title"))}</span></button>'
    )


# --- bridge ----------------------------------------------------------------


def open_grid(deck_id: int) -> None:
    global _active
    from . import quizlet

    # One webview, one screen in it. Opening either has to put the other away,
    # or leaving this one would drop the user back inside a half-finished
    # study session they never asked to resume.
    quizlet.close()
    options = _options()
    _active = {
        "deck": int(deck_id),
        "ids": _card_ids(int(deck_id), options["sort"]),
        "page": 0,
    }
    _redraw()


def command(rest: str) -> None:
    if rest.startswith("open:"):
        try:
            open_grid(int(rest[len("open:"):]))
        except (TypeError, ValueError):
            pass
        return
    if _active is None:
        return

    if rest == "close":
        close()
        # `refresh` here and not `_renderPage`: leaving the grid goes back to
        # the counts page, and that page *is* the counts.
        try:
            mw.overview.refresh()
        except Exception:
            _redraw()
    elif rest.startswith("page:"):
        try:
            _active["page"] = int(rest[len("page:"):])
        except (TypeError, ValueError):
            return
        _send(_payload())
    elif rest.startswith("opt:"):
        parts = rest[len("opt:"):].split(":", 1)
        if len(parts) != 2:
            return
        name, raw = parts
        # Keep the first tile that was on screen on screen. Without it, going
        # from twelve per page to eight jumps the reader somewhere unrelated
        # and the size control reads as though it also scrolled.
        first = _active["page"] * grid.per_page(_options())
        if _set_option(name, raw):
            _active["ids"] = _card_ids(_active["deck"], _options()["sort"])
            _active["page"] = 0
        else:
            _active["page"] = grid.page_for_index(first,
                                                  grid.per_page(_options()))
        _send(_payload())


def install_hooks() -> None:
    """Leave the overview and the grid is closed.

    It lives in the overview's webview, so anything that navigates away has
    already destroyed it; keeping `_active` set would drop the user back into
    the grid the next time they opened *any* deck.
    """
    from aqt import gui_hooks

    def on_state(new_state, *_args):
        if new_state != "overview":
            close()

    gui_hooks.state_did_change.append(on_state)
