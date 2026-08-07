"""Deck overview renderer — replaces Overview._renderPage.

Rebuilds the screen you land on after clicking a deck: back link, deck header,
three count cards, one primary study button, a 7-day forecast and quiet footer
actions. Anki's own top/bottom bars
are hidden here (the page carries its own back link and actions), and every
action reuses Anki's native overview commands so behaviour is unchanged.
"""

import html

from aqt import mw
from aqt.overview import Overview

from ..core import conf
from ..core.translations import tr, weekday_short

_original_render_page = Overview._renderPage


def _deck_tint(did: int) -> str:
    from .dashboard import SIDE_TINTS

    return SIDE_TINTS[did % len(SIDE_TINTS)]


def _glyph(name: str) -> str:
    stripped = (name or "").strip()
    # Deck names are usually "Parent::Child"; the leaf reads better as an icon.
    leaf = stripped.rsplit("::", 1)[-1].strip()
    return html.escape(leaf[:1].upper()) if leaf else "•"


def _description(deck) -> str:
    """The deck's own description, rendered the way Anki renders it."""
    if deck.get("dyn"):
        return ""
    text = (deck.get("desc") or "").strip()
    if not text:
        return ""
    if deck.get("md"):
        try:
            return mw.col.render_markdown(text)
        except Exception:
            pass
    return text


def _forecast(did: int, days: int = 7) -> list:
    """Cards already scheduled to come due on each of the next `days` days.

    Straight from the scheduler's own due dates — with FSRS enabled those are
    exactly the intervals FSRS picked. `odid` is matched too, so cards this
    deck has lent to a filtered deck still count.
    """
    try:
        deck_ids = mw.col.decks.deck_and_child_ids(did)
        ids = ",".join(str(int(d)) for d in deck_ids)
        today = mw.col.sched.today
        rows = mw.col.db.all(
            f"select due - ?, count() from cards "
            f"where (did in ({ids}) or odid in ({ids})) "
            "and queue in (2, 3) and due >= ? and due < ? group by due",
            today,
            today,
            today + days,
        )
        counts = {int(day): int(count) for day, count in rows}
    except Exception as e:
        print(f"[Awesome Dashboard] overview forecast failed: {e}")
        return []
    return [counts.get(index, 0) for index in range(days)]


def _forecast_html(did: int) -> str:
    values = _forecast(did)
    if not values or not any(values):
        return ""
    peak = max(values)
    from datetime import date, timedelta

    today = date.today()
    bars = []
    for index, value in enumerate(values):
        # Keep small non-zero days visible instead of collapsing to a hairline.
        height = max(8, round(value / peak * 100)) if value else 0
        day = today + timedelta(days=index)
        label = tr("today_short") if index == 0 else weekday_short(day.weekday())
        bars.append(
            f'<div class="awd-ov-bar">'
            f'<span class="awd-ov-bar-n">{value}</span>'
            f'<div class="awd-ov-bar-track"><i style="height:{height}%"></i></div>'
            f'<span class="awd-ov-bar-d">{html.escape(label)}</span>'
            f"</div>"
        )
    return f"""
    <section class="awd-ov-card awd-ov-forecast">
      <div class="awd-ov-card-title">{tr("forecast_7")}</div>
      <div class="awd-ov-bars">{"".join(bars)}</div>
    </section>
    """


def _children_html(did: int) -> str:
    try:
        tree = mw.col.sched.deck_due_tree(did)
    except Exception:
        return ""
    children = getattr(tree, "children", None) or []
    if not children:
        return ""
    rows = []
    for child in children:
        child_id = int(child.deck_id)
        tint = _deck_tint(child_id)
        total = child.new_count + child.learn_count + child.review_count
        rows.append(
            f'<div class="awd-ov-sub" onclick="pycmd(\'awd:opendeck:{child_id}\')">'
            f'<span class="awd-ov-sub-ic" style="background:{tint}21;color:{tint}">'
            f"{_glyph(child.name)}</span>"
            f'<span class="awd-ov-sub-name">{html.escape(child.name)}</span>'
            f'<span class="awd-ov-sub-n">{total} {tr("cards_unit")}</span>'
            f"</div>"
        )
    return f"""
    <section class="awd-ov-card awd-ov-subs">
      <div class="awd-ov-card-title">{tr("subdecks")}</div>
      {"".join(rows)}
    </section>
    """


def _footer_html(deck) -> str:
    links = []
    if deck.get("dyn"):
        links.append(("refresh", tr("rebuild_deck")))
        links.append(("empty", tr("empty_deck")))
    links.append(("opts", tr("deck_options")))
    if not deck.get("dyn"):
        links.append(("studymore", tr("custom_study")))
    links.append(("awd:deck:rename", tr("deck_rename")))
    links.append(("awd:deck:export", tr("deck_export")))
    links.append(("description", tr("deck_description")))
    try:
        if mw.col.sched.have_buried():
            links.append(("unbury", tr("unbury")))
    except Exception:
        pass
    items = "".join(
        f'<span class="awd-ov-link" onclick="pycmd(\'{cmd}\')">{html.escape(label)}</span>'
        for cmd, label in links
    )
    return f'<footer class="awd-ov-footer">{items}</footer>'


def render_page(self: Overview) -> None:
    if not mw.col:
        return
    if not conf.get().get("styleOverview", True):
        return _original_render_page(self)

    deck = mw.col.decks.current()
    # Keep the attributes the native "shared deck" link handler relies on.
    self.sid = deck.get("sharedFrom")
    if self.sid:
        self.sidVer = deck.get("ver", None)

    try:
        if mw.col.sched._is_finished():
            # Anki's congrats page already covers this state well.
            return self._show_finished_screen()
    except Exception:
        pass

    try:
        did = int(deck["id"])
    except (KeyError, TypeError, ValueError):
        return _original_render_page(self)

    new_count, learn_count, review_count = mw.col.sched.counts()
    total = new_count + learn_count + review_count
    tint = _deck_tint(did)
    name = html.escape(str(deck.get("name", "")).rsplit("::", 1)[-1])
    description = _description(deck)
    desc_html = (
        f'<div class="awd-ov-desc">{description}</div>' if description else ""
    )

    counts_html = "".join(
        f'<div class="awd-ov-count {cls}">'
        f'<div class="awd-ov-count-label">{label}</div>'
        f'<div class="awd-ov-count-value">{value}</div></div>'
        for cls, label, value in (
            ("new", tr("count_new"), new_count),
            ("learn", tr("count_learn"), learn_count),
            ("due", tr("count_due"), review_count),
        )
    )

    if total:
        button = (
            f'<button class="awd-ov-study" onclick="pycmd(\'study\')">'
            f'{tr("study_now")} · {total} {tr("cards_unit")}</button>'
            f'<div class="awd-ov-study-hint">{tr("space_to_start")}</div>'
        )
    else:
        button = (
            f'<button class="awd-ov-study" onclick="pycmd(\'study\')">'
            f'{tr("study_now")}</button>'
            f'<div class="awd-ov-study-hint">{tr("nothing_due")}</div>'
        )

    body = f"""
    <div class="awd-ov">
      <div class="awd-ov-top">
        <span class="awd-ov-back" onclick="pycmd('decks')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 5.5 8.5 12l6.5 6.5"/>
          </svg>
          <span>{tr("home")}</span>
        </span>
      </div>
      <header class="awd-ov-head">
        <span class="awd-ov-icon" style="background:{tint}21;color:{tint}">{_glyph(str(deck.get("name", "")))}</span>
        <div class="awd-ov-headtext">
          <h1 class="awd-ov-name">{name}</h1>
          {desc_html}
        </div>
      </header>
      <section class="awd-ov-counts">{counts_html}</section>
      <section class="awd-ov-studybox">{button}</section>
      {_forecast_html(did)}
      {_children_html(did)}
      {_footer_html(deck)}
    </div>
    <script>
      // The native overview started studying on Space via an autofocused
      // button; this page has no focused control, so bind the key directly.
      document.addEventListener("keydown", function (event) {{
        if (event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;
        if (event.key === " " || event.key === "Enter") {{
          event.preventDefault();
          pycmd("study");
        }}
      }});
    </script>
    """

    self.web.stdHtml(body=body, css=[], js=[], context=self)
    try:
        # Keep the native bottom bar's content in sync even though it stays
        # hidden here — turning the redesign off must not leave it stale.
        self._renderBottom()
    except Exception:
        pass
    from . import dashboard

    dashboard.apply_bar_visibility("overview")


def install() -> None:
    Overview._renderPage = render_page
