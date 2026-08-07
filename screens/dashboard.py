"""Dashboard renderer — replaces DeckBrowser._renderPage.

Builds the deck-browser page: greeting, stat cards, heatmap, Pomodoro and the
deck list. Deck interactions reuse Anki's own bridge commands, so native
behaviour like the options menu keeps working.
"""

import html
import json
from datetime import datetime

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser

from ..core import conf, stats, themes
from ..core.translations import (
    current_lang,
    date_format,
    day_month_format,
    fmt_int,
    month_name,
    tr,
    weekday_name,
)
from ..features import pomodoro

ICONS = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "chart": '<path d="M5 20v-7M11 20V5M17 20v-11"/><path d="M3 20h18"/>',
    "sync": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/>'
               '<path d="M1 14h6M9 8h6M17 16h6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "card": '<rect x="3.5" y="5.5" width="17" height="13" rx="2.5"/><path d="M3.5 10.5h17"/>',
    "chevron": '<path d="m9 6 6 6-6 6"/>',
    "funnel": '<path d="M4 5h16l-6 7v5l-4 2v-7z"/>',
    "download": '<path d="M12 4v12M6 11l6 6 6-6"/><path d="M4 21h16"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
             '<path d="M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
    "kebab": '<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
    "book": '<path d="M2 4h7a3 3 0 0 1 3 3v13a2.5 2.5 0 0 0-2.5-2.5H2z"/>'
            '<path d="M22 4h-7a3 3 0 0 0-3 3v13a2.5 2.5 0 0 1 2.5-2.5H22z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "inbox": '<path d="M22 13h-5l-2 3h-6l-2-3H2"/>'
             '<path d="M5.5 6 2 13v5a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5l-3.5-7a2 2 0 0 0-1.8-1.1H7.3A2 2 0 0 0 5.5 6z"/>',
    "power": '<path d="M12 3v8"/><path d="M17.7 6.3a8 8 0 1 1-11.4 0"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    "sidebar": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9.5 4v16"/>',
    "grid": '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/>'
            '<rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/>',
    "check": '<path d="M4.5 12.5l4.8 4.8L19.5 7"/>',
}


def icon(name: str, cls: str = "") -> str:
    return (
        f'<svg class="awd-icon {cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        f' stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
        f' aria-hidden="true">{ICONS[name]}</svg>'
    )


# --- header ------------------------------------------------------------------

def _greeting(config: dict) -> str:
    custom = (config.get("customGreeting") or "").strip()
    if custom:
        return html.escape(custom)
    hour = datetime.now().hour
    if hour < 11:
        key = "greeting_morning"
    elif hour < 18:
        key = "greeting_afternoon"
    else:
        key = "greeting_evening"
    name = (config.get("userName") or "").strip()
    if not name:
        try:
            name = mw.pm.name or ""
        except Exception:
            name = ""
    suffix = f", {html.escape(name)}" if name else ""
    return f"{tr(key)}{suffix}"


def _date_line() -> str:
    today = datetime.now()
    return (
        date_format()
        .replace("{weekday}", weekday_name(today.weekday()))
        .replace("{month}", month_name(today.month))
        .replace("{day}", str(today.day))
    )


def _events_html(config: dict) -> str:
    """Exam-countdown badges under the greeting. Past events are hidden."""
    events = config.get("events") or []
    if not isinstance(events, list):
        return ""
    today = datetime.now().date()
    upcoming = []
    for event in events:
        if not isinstance(event, dict):
            continue
        name = str(event.get("name") or "").strip()
        raw_date = str(event.get("date") or "")
        try:
            when = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        days = (when - today).days
        if name and days >= 0:
            upcoming.append((days, name))
    if not upcoming:
        return ""
    badges = []
    for days, name in sorted(upcoming):
        if days == 0:
            label = tr("event_today")
        else:
            label = tr("event_days_left", n=fmt_int(days))
        soon = " soon" if days <= 14 else ""
        badges.append(
            f'<span class="awd-event{soon}">🎯 <b>{html.escape(name)}</b>'
            f'&nbsp;·&nbsp;<span class="awd-event-days">{label}</span></span>'
        )
    return f'<div class="awd-events">{"".join(badges)}</div>'


def _header_html(config: dict) -> str:
    actions = [
        ("awd:add", "plus", tr("add")),
        ("awd:browse", "search", tr("browse")),
        ("awd:stats", "chart", tr("stats")),
        ("awd:sync", "sync", tr("sync")),
    ]
    pills = "".join(
        f'<button class="awd-pill" onclick="pycmd(\'{cmd}\')">'
        f'{icon(name)}<span>{html.escape(label)}</span></button>'
        for cmd, name, label in actions
    )
    pills += (
        f'<button class="awd-pill awd-pill-icon" title="{html.escape(tr("restart_tip"))}"'
        f' onclick="pycmd(\'awd:restart\')">{icon("power")}</button>'
    )
    pills += (
        f'<button class="awd-pill awd-pill-icon" title="{html.escape(tr("settings"))}"'
        f' onclick="pycmd(\'awd:settings\')">{icon("sliders")}</button>'
    )
    return f"""
    <header class="awd-header awd-card">
      <div class="awd-header-text">
        <span class="awd-chip">{tr("dashboard")}</span>
        <h1 class="awd-greeting">{_greeting(config)}</h1>
        <div class="awd-date">{_date_line()}</div>
        {_events_html(config)}
      </div>
      <nav class="awd-actions">{pills}</nav>
    </header>
    """


# --- stat cards ----------------------------------------------------------------

def _stat_card(icon_name: str, label: str, value: str, unit: str, footer: str = "", emoji: str = "") -> str:
    badge = f'<span class="awd-stat-emoji">{emoji}</span>' if emoji else icon(icon_name)
    footer_html = f'<div class="awd-stat-footer">{footer}</div>' if footer else ""
    return f"""
    <div class="awd-card awd-stat">
      <div class="awd-stat-top">
        <span class="awd-stat-label">{label}</span>
        <span class="awd-stat-badge">{badge}</span>
      </div>
      <div class="awd-stat-value">{value}<span class="awd-stat-unit">{unit}</span></div>
      {footer_html}
    </div>
    """


def _stats_row_html(bundle: dict, due_total: int) -> str:
    cards_today = bundle.get("cards_today", 0)
    minutes = bundle.get("minutes_today", 0.0)
    minutes_text = f"{minutes:.0f}" if minutes >= 10 else f"{minutes:.1f}"
    retention = bundle.get("retention")
    retention_text = f"{retention:.0f}%" if retention is not None else "–"
    streak = bundle.get("streak", 0)
    longest = bundle.get("longest_streak", 0)

    done_ratio = 0.0
    if cards_today + due_total > 0:
        done_ratio = cards_today / (cards_today + due_total)
    progress = (
        f'<div class="awd-progress"><i style="width:{done_ratio * 100:.0f}%"></i></div>'
    )

    # With FSRS on, the measured retention is only meaningful next to the
    # target the scheduler is aiming for.
    retention_footer = ""
    try:
        from ..features import fsrs

        if fsrs.is_enabled():
            current = mw.col.decks.get_config(mw.col.decks.get_current_id() or 1)
            target = round(fsrs.desired_retention(current) * 100)
            retention_footer = tr("fsrs_target", n=f"{target}%")
    except Exception:
        pass

    cards = [
        _stat_card("book", tr("studied_today"), fmt_int(cards_today), tr("cards_unit")),
        _stat_card("clock", tr("minutes_label"), minutes_text, tr("minutes_unit")),
        _stat_card("", tr("streak"), fmt_int(streak), tr("days_unit"),
                   footer=f'{tr("longest_streak")}: {fmt_int(longest)}', emoji="🔥"),
        _stat_card("target", tr("retention"), retention_text, "", footer=retention_footer),
        _stat_card("inbox", tr("due_today"), fmt_int(due_total), tr("cards_unit"), footer=progress),
    ]
    return f'<section class="awd-stats">{"".join(cards)}</section>'


# --- heatmap & pomodoro shells (filled in by web/dashboard/dashboard.js) ------

def _heatmap_card_html(bundle: dict) -> str:
    streak = fmt_int(bundle.get("streak", 0))
    longest = fmt_int(bundle.get("longest_streak", 0))
    avg = bundle.get("daily_avg", 0.0)
    return f"""
    <div class="awd-card awd-heatmap-card">
      <div class="awd-card-head">
        <span class="awd-chip">{tr("activity")}</span>
        <div class="awd-streak-badge" title="{tr("streak").title()}">
          <span class="awd-streak-flame">🔥</span>
          <b>{streak}</b>&nbsp;{tr("days_unit")}
          <span class="awd-streak-sub">· {tr("longest_streak")} {longest} · {tr("daily_avg")} {avg:.0f}</span>
        </div>
      </div>
      <div id="awd-hm-years" class="awd-hm-years"></div>
      <div id="awd-heatmap" class="awd-heatmap"></div>
      <div class="awd-heatmap-legend">
        <span>{tr("less")}</span>
        <i class="l0"></i><i class="l1"></i><i class="l2"></i><i class="l3"></i><i class="l4"></i>
        <span>{tr("more")}</span>
      </div>
    </div>
    """


def _pomodoro_card_html() -> str:
    return f"""
    <div class="awd-card awd-pom-card">
      <div class="awd-card-head">
        <span class="awd-chip" id="awd-pom-phase">{tr("pomodoro_idle")}</span>
        <span class="awd-pom-sessions" id="awd-pom-sessions"></span>
      </div>
      <div class="awd-pom-ring">
        <svg viewBox="0 0 120 120">
          <circle class="awd-ring-track" cx="60" cy="60" r="52"/>
          <circle class="awd-ring-fill" id="awd-pom-ring" cx="60" cy="60" r="52"
                  stroke-dasharray="326.7" stroke-dashoffset="326.7"/>
        </svg>
        <div class="awd-pom-time" id="awd-pom-time">--:--</div>
      </div>
      <div class="awd-pom-controls">
        <button class="awd-pill awd-pill-accent" id="awd-pom-toggle"
                onclick="pycmd('awd:pom:toggle')">{tr("start")}</button>
        <button class="awd-pill awd-pill-ghost" id="awd-pom-reset"
                onclick="pycmd('awd:pom:reset')">{tr("reset")}</button>
        <button class="awd-pill awd-pill-ghost" id="awd-pom-skip" hidden
                onclick="pycmd('awd:pom:skip')">{tr("skip")}</button>
      </div>
    </div>
    """


# --- deck list -------------------------------------------------------------------

def _count_pills(node) -> str:
    parts = []
    for value, cls in ((node.new_count, "new"), (node.learn_count, "learn"), (node.review_count, "due")):
        if value:
            parts.append(f'<span class="awd-count {cls}">{fmt_int(value)}</span>')
    if not parts:
        return f'<span class="awd-count zero">{tr("done_chip")}</span>'
    return "".join(parts)


def _deck_row_html(node, depth: int) -> str:
    did = int(node.deck_id)
    name = html.escape(node.name)
    has_children = bool(node.children)
    if has_children:
        chevron_cls = "awd-caret" + (" closed" if node.collapsed else "")
        caret = (
            f'<button class="{chevron_cls}"'
            f' onclick="Awd.toggleDeck(event, {did})">{icon("chevron")}</button>'
        )
    else:
        caret = '<span class="awd-caret spacer"></span>'
    if getattr(node, "filtered", False):
        deck_icon = icon("funnel", "awd-deck-glyph filtered")
    elif has_children:
        deck_icon = icon("folder", "awd-deck-glyph")
    else:
        deck_icon = icon("card", "awd-deck-glyph")
    return f"""
    <div class="awd-deck-row" data-did="{did}" style="--depth:{depth}"
         onclick="pycmd('open:{did}')">
      {caret}
      {deck_icon}
      <span class="awd-deck-name">{name}</span>
      <span class="awd-counts">{_count_pills(node)}</span>
    </div>
    """


def _deck_group_html(node, depth: int) -> str:
    """A deck row plus its children, which stay in the DOM even when collapsed —
    expanding is a class toggle, not a re-render.
    """
    row = _deck_row_html(node, depth)
    if not node.children:
        return f'<div class="awd-deck-group">{row}</div>'
    closed = " closed" if node.collapsed else ""
    inner = "".join(_deck_group_html(child, depth + 1) for child in node.children)
    return (
        f'<div class="awd-deck-group">{row}'
        f'<div class="awd-deck-children{closed}">'
        f'<div class="awd-deck-children-inner">{inner}</div>'
        f"</div></div>"
    )


def _deck_rows_html(node, depth: int = 0) -> str:
    return "".join(_deck_group_html(child, depth) for child in node.children)


def _decks_card_html(tree) -> str:
    rows = _deck_rows_html(tree)
    if not rows:
        rows = f"""
        <div class="awd-empty">
          <div class="awd-empty-title">{tr("empty_title")}</div>
          <div class="awd-empty-hint">{tr("empty_hint")}</div>
        </div>
        """
    return f"""
    <section class="awd-card awd-decks">
      <div class="awd-card-head">
        <span class="awd-chip">{tr("decks")}</span>
        <span class="awd-decks-hint">{tr("deck_header_hint")}</span>
      </div>
      <div class="awd-deck-list">{rows}</div>
    </section>
    """


def _footer_html() -> str:
    buttons = [
        ("create", "plus", tr("create_deck")),
        ("import", "download", tr("import_file")),
        ("shared", "globe", tr("get_shared")),
    ]
    pills = "".join(
        f'<button class="awd-pill awd-pill-ghost" onclick="pycmd(\'{cmd}\')">'
        f'{icon(name)}<span>{html.escape(label)}</span></button>'
        for cmd, name, label in buttons
    )
    return f'<footer class="awd-footer">{pills}</footer>'


# --- sidebar (full 288px / compact rail / hidden) ---------------------------------

# Fixed per-deck tints, Apple system palette — same trick as the deck icons:
# a stable color derived from the deck id.
SIDE_TINTS = [
    "#FF375F", "#007AFF", "#AF52DE", "#FF9500",
    "#34C759", "#5856D6", "#00C7BE", "#FF2D55",
]


def _deck_tint(did: int) -> str:
    return SIDE_TINTS[did % len(SIDE_TINTS)]


def _deck_glyph(name: str) -> str:
    """First character of the deck name as its icon (日 / A / 漢 ...)."""
    stripped = (name or "").strip()
    return html.escape(stripped[:1].upper()) if stripped else "•"


def _display_name(config: dict) -> str:
    name = (config.get("userName") or "").strip()
    if not name:
        try:
            name = mw.pm.name or ""
        except Exception:
            name = ""
    return name or "Anki"


def _side_counts(node) -> str:
    parts = []
    for value, cls in ((node.new_count, "new"), (node.learn_count, "learn"), (node.review_count, "due")):
        if value:
            parts.append(f'<span class="awd-sd-count {cls}">{fmt_int(value)}</span>')
    if not parts:
        return icon("check", "awd-sd-check")
    return "".join(parts)


def _side_deck_group(node, depth: int) -> str:
    did = int(node.deck_id)
    name = html.escape(node.name)
    tint = _deck_tint(did)
    has_children = bool(node.children)
    if has_children:
        caret_cls = "awd-sd-caret" + (" closed" if node.collapsed else "")
        caret = (
            f'<button class="{caret_cls}"'
            f' onclick="Awd.toggleDeck(event, {did})">{icon("chevron")}</button>'
        )
    else:
        caret = '<span class="awd-sd-caret spacer"></span>'
    row = f"""
    <div class="awd-sd-row" data-did="{did}" style="--sd:{depth}"
         onclick="pycmd('open:{did}')">
      {caret}
      <span class="awd-sd-ic" style="background:{tint}21;color:{tint}">{_deck_glyph(node.name)}</span>
      <span class="awd-sd-name">{name}</span>
      <span class="awd-sd-counts">{_side_counts(node)}</span>
    </div>
    """
    lower_name = html.escape(node.name.lower(), quote=True)
    if not has_children:
        return f'<div class="awd-sd-group" data-name="{lower_name}">{row}</div>'
    closed = " closed" if node.collapsed else ""
    inner = "".join(_side_deck_group(child, depth + 1) for child in node.children)
    return (
        f'<div class="awd-sd-group" data-name="{lower_name}">{row}'
        f'<div class="awd-sd-children{closed}">'
        f'<div class="awd-sd-children-inner">{inner}</div>'
        f"</div></div>"
    )


def _side_nav_items() -> str:
    items = [
        ("awd:add", "plus", tr("add_note")),
        ("awd:browse", "grid", tr("browse_cards")),
        ("awd:stats", "chart", tr("stats")),
        ("awd:sync", "sync", tr("sync")),
    ]
    rows = (
        f'<a class="awd-side-item active">{icon("home")}<span>{html.escape(tr("home"))}</span></a>'
    )
    rows += "".join(
        f'<a class="awd-side-item" onclick="pycmd(\'{cmd}\')">'
        f'{icon(ic)}<span>{html.escape(label)}</span></a>'
        for cmd, ic, label in items
    )
    return rows


def _sidebar_html(config: dict, tree, due_total: int) -> str:
    name = _display_name(config)
    rows = "".join(_side_deck_group(child, 0) for child in tree.children)
    if not rows:
        rows = f'<div class="awd-sd-empty">{tr("empty_title")}</div>'
    footer_items = [
        ("create", "plus", tr("new_deck")),
        ("import", "download", tr("import_file")),
        ("shared", "globe", tr("get_shared")),
    ]
    footer = "".join(
        f'<a class="awd-side-item ghost" onclick="pycmd(\'{cmd}\')">'
        f'{icon(ic)}<span>{html.escape(label)}</span></a>'
        for cmd, ic, label in footer_items
    )
    return f"""
    <aside class="awd-side">
      <div class="awd-side-user">
        <div class="awd-side-avatar">{_deck_glyph(name)}</div>
        <div class="awd-side-user-text">
          <div class="awd-side-name">{html.escape(name)}</div>
          <div class="awd-side-sub">{_date_line()}</div>
        </div>
        <button class="awd-side-btn" title="{html.escape(tr("sidebar_toggle_tip"))}"
                onclick="Awd.sideToggle()">{icon("sidebar")}</button>
      </div>
      <nav class="awd-side-nav">{_side_nav_items()}</nav>
      <div class="awd-side-decksec">
        <span class="awd-side-heading">{tr("decks")}</span>
        <span class="awd-side-due">{fmt_int(due_total)} {tr("due_short")}</span>
      </div>
      <div class="awd-side-search">
        {icon("search")}
        <input id="awd-side-q" placeholder="{html.escape(tr("search_decks"))}"
               oninput="Awd.sideFilter(this.value)" spellcheck="false">
      </div>
      <div class="awd-side-decks" id="awd-side-decks">{rows}</div>
      <div class="awd-side-foot">{footer}</div>
    </aside>
    """


def _sidebar_mini_html(config: dict, tree) -> str:
    name = _display_name(config)
    nav_items = [
        ("awd:add", "plus", tr("add_note")),
        ("awd:browse", "grid", tr("browse_cards")),
        ("awd:stats", "chart", tr("stats")),
        ("awd:sync", "sync", tr("sync")),
    ]
    nav = f'<button class="awd-mini-btn active" title="{html.escape(tr("home"))}">{icon("home")}</button>'
    nav += "".join(
        f'<button class="awd-mini-btn" title="{html.escape(label)}"'
        f' onclick="pycmd(\'{cmd}\')">{icon(ic)}</button>'
        for cmd, ic, label in nav_items
    )
    decks = ""
    for child in tree.children:
        did = int(child.deck_id)
        tint = _deck_tint(did)
        due = child.new_count + child.learn_count + child.review_count
        dot = '<span class="awd-mini-dot"></span>' if due else ""
        decks += (
            f'<button class="awd-mini-deck" title="{html.escape(child.name)}"'
            f' style="background:{tint}21;color:{tint}"'
            f' onclick="pycmd(\'open:{did}\')">{_deck_glyph(child.name)}{dot}</button>'
        )
    return f"""
    <aside class="awd-side-mini">
      <button class="awd-side-btn" title="{html.escape(tr("sidebar_toggle_tip"))}"
              onclick="Awd.sideToggle()">{icon("sidebar")}</button>
      <div class="awd-side-avatar small" title="{html.escape(name)}">{_deck_glyph(name)}</div>
      <div class="awd-mini-sep"></div>
      {nav}
      <div class="awd-mini-sep"></div>
      <div class="awd-mini-decks">{decks}</div>
      <button class="awd-mini-btn ghost" title="{html.escape(tr("new_deck"))}"
              onclick="pycmd('create')">{icon("plus")}</button>
    </aside>
    """


def _topline_html() -> str:
    """Slim chrome row shown while the sidebar is visible — the actions that
    the (hidden) dashboard header would otherwise provide."""
    buttons = [
        ("awd:sync", "sync", tr("sync")),
        ("awd:settings", "sliders", tr("settings")),
        ("awd:restart", "power", tr("restart_tip")),
    ]
    right = "".join(
        f'<button class="awd-iconbtn" title="{html.escape(label)}"'
        f' onclick="pycmd(\'{cmd}\')">{icon(ic)}</button>'
        for cmd, ic, label in buttons
    )
    return (
        '<div class="awd-topline">'
        f'<span class="awd-topline-title">{html.escape(tr("home"))}</span>'
        '<span class="awd-topline-spacer"></span>'
        f"{right}</div>"
    )


def _greet_bare_html(config: dict) -> str:
    """Design-style greeting (bare h1, no card) — used when the sidebar is
    visible and the header card (with its action pills) is hidden."""
    return f"""
    <section class="awd-greet-bare">
      <h1 class="awd-greeting">{_greeting(config)}</h1>
      <div class="awd-date">{_date_line()}</div>
      {_events_html(config)}
    </section>
    """


# --- native bar visibility --------------------------------------------------------

class _BarGuard:
    """Qt event filter: re-hides a native bar whenever something shows it over
    the dashboard. Anki 26's auto-hide machinery re-shows bars on mouse events
    and via delayed callbacks, so a one-shot hide() loses the race."""

    def __new__(cls, *args):
        from aqt.qt import QObject

        class _Impl(QObject):
            def __init__(self, widget, slot):
                super().__init__(widget)
                self._widget = widget
                self._slot = slot  # 0 = bottom bar, 1 = top toolbar
                self.stats = {"shows": 0, "hides": 0, "last_show_stack": []}

            def eventFilter(self, obj, event):
                try:
                    from aqt.qt import QEvent, QTimer

                    show_type = getattr(QEvent, "Type", QEvent).Show
                    if event.type() == show_type:
                        self.stats["shows"] += 1
                        if bars_hidden_for(mw.state, conf.get())[self._slot]:
                            import traceback

                            self.stats["last_show_stack"] = [
                                f"{frame.name}:{frame.lineno}"
                                f"({frame.filename.rsplit('/', 1)[-1]})"
                                for frame in traceback.extract_stack()[-8:-1]
                            ]
                            self.stats["hides"] += 1
                            widget = self._widget
                            QTimer.singleShot(
                                0, lambda: _force_bar_visible(widget, False)
                            )
                except Exception:
                    pass
                return False

        return _Impl(*args)


_bar_guards = []


def _install_show_blocker(widget, slot: int) -> None:
    """Swallow .show() calls aimed at a bar on screens that hide it.

    Anki's mouse-leave auto-reveal shows the bar and our guard re-hides it a tick
    later; that one-frame flash resizes the webview and reads as the page jerking.
    QWidget.setVisible still works, so _force_bar_visible can bring it back.
    """
    if getattr(widget, "_awd_show_blocked", False):
        return
    original_show = widget.show

    def guarded_show():
        try:
            if bars_hidden_for(mw.state, conf.get())[slot]:
                return
        except Exception:
            pass
        original_show()

    widget.show = guarded_show
    widget._awd_show_blocked = True


def install_bar_guards() -> None:
    if _bar_guards:
        return
    for widget, slot in (
        (getattr(mw, "bottomWeb", None), 0),
        (getattr(mw, "toolbarWeb", None), 1),
    ):
        if widget is None:
            continue
        try:
            guard = _BarGuard(widget, slot)
            widget.installEventFilter(guard)
            _bar_guards.append(guard)
            _install_show_blocker(widget, slot)
        except Exception as e:
            print(f"[Awesome Dashboard] bar guard install failed for slot {slot}: {e}")
    mw._awd_bar_guards = _bar_guards


def _force_bar_visible(widget, visible: bool) -> None:
    """Truly show/hide one of Anki's bar webviews.

    Anki 26's ToolbarWebView.hide()/show() are logical: they collapse the bar to
    1px but keep the widget visible, and adjustHeightToFit() later resurrects it.
    QWidget.setVisible bypasses those overrides.
    """
    from aqt.qt import QWidget

    if visible:
        QWidget.setVisible(widget, True)
        widget.show()  # native logical show: restores height bookkeeping
    else:
        widget.hide()  # native logical hide: keeps Anki's own flags in sync
        QWidget.setVisible(widget, False)


def bars_hidden_for(state: str, config: dict) -> tuple:
    """(hide_bottom, hide_top) for a given main-window state.

    The dashboard hides the bars it replaces with its own pills; the overview hides
    both, since it carries its own back link and footer actions.
    """
    if state == "deckBrowser":
        return (
            bool(config.get("hideNativeBottomBar", True)),
            bool(config.get("hideNativeToolbar", False)),
        )
    if state == "overview" and config.get("styleOverview", True):
        return (True, True)
    if state == "review" and config.get("styleReviewer", True):
        # The reviewer page draws its own header and answer bar.
        return (True, True)
    return (False, False)


def apply_bar_visibility(state: str) -> None:
    """Show or hide Anki's native top/bottom bars for the current screen.

    Each widget gets its own try/except so one failure can't strand the other.
    """
    install_bar_guards()
    hide_bottom, hide_top = bars_hidden_for(state, conf.get())

    try:
        _force_bar_visible(mw.bottomWeb, not hide_bottom)
    except Exception as e:
        print(f"[Awesome Dashboard] bottom bar visibility failed: {e}")

    try:
        _force_bar_visible(mw.toolbarWeb, not hide_top)
    except Exception as e:
        print(f"[Awesome Dashboard] toolbar visibility failed: {e}")


def _fake_calendar(real: dict) -> dict:
    """Dev helper (hidden config key `debugFakeYears`): synthesize several
    years of plausible-looking activity so the heatmap's year picker can be
    tested. Display-only — the collection and real stats stay untouched."""
    import hashlib
    from datetime import date, timedelta

    today = date.today()
    fake = dict(real)
    cursor = date(today.year - 3, 1, 1)
    while cursor <= today:
        key = cursor.strftime("%Y-%m-%d")
        if key not in fake:
            digest = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
            # ~72% of days active; intensity waves by weekday and month so the
            # texture looks organic (quiet summers, strong weekday streaks).
            if digest % 100 < 72:
                base = (digest >> 8) % 45
                weekday_boost = 15 if cursor.weekday() < 5 else 0
                month_wave = (cursor.month * 7 + (digest >> 16) % 10) % 25
                fake[key] = 1 + base + weekday_boost + month_wave
        cursor += timedelta(days=1)
    return fake


# --- page assembly ----------------------------------------------------------------

def _render_data_for(tree):
    """Native _collapse/_delete resolve decks through self._render_data.tree."""
    current_id = 1
    try:
        current_id = mw.col.decks.get_current_id()
    except Exception:
        try:
            current_id = mw.col.decks.current()["id"]
        except Exception:
            pass
    studied = ""
    try:
        studied = mw.col.studied_today()
    except Exception:
        pass
    try:
        from aqt.deckbrowser import RenderData
        return RenderData(
            tree=tree,
            current_deck_id=current_id,
            studied_today=studied,
            sched_upgrade_required=False,
        )
    except Exception:
        from types import SimpleNamespace
        return SimpleNamespace(tree=tree)


def render_page(self: DeckBrowser, reuse: bool = False) -> None:
    if not self.mw.col:
        return
    config = conf.get()
    bundle = stats.gather()

    tree = self.mw.col.sched.deck_due_tree()
    self._render_data = _render_data_for(tree)
    new_n, learn_n, review_n = stats.due_counts(tree)
    due_total = new_n + learn_n + review_n

    sidebar_mode = config.get("sidebarMode", "hidden")
    if sidebar_mode not in ("full", "compact", "hidden"):
        sidebar_mode = "hidden"

    # The bare greeting replaces the header card while the sidebar is shown;
    # both live in the DOM, CSS mode classes decide which one is visible.
    sections = [_greet_bare_html(config), _header_html(config)]
    if config.get("showStats", True):
        sections.append(_stats_row_html(bundle, due_total))
    show_heatmap = config.get("showHeatmap", True)
    show_pomodoro = config.get("showPomodoro", True)
    if show_heatmap or show_pomodoro:
        middle = ""
        if show_heatmap:
            middle += _heatmap_card_html(bundle)
        if show_pomodoro:
            middle += _pomodoro_card_html()
        mode = "both" if (show_heatmap and show_pomodoro) else "single"
        sections.append(f'<section class="awd-middle {mode}">{middle}</section>')
    sections.append(_decks_card_html(tree))
    sections.append(_footer_html())

    heatmap_calendar = bundle.get("calendar", {})
    if config.get("debugFakeYears", False):
        heatmap_calendar = _fake_calendar(heatmap_calendar)

    js_data = {
        "calendar": heatmap_calendar,
        "todayKey": bundle.get("today_key", ""),
        "showHeatmap": show_heatmap,
        "showPomodoro": show_pomodoro,
        "pom": pomodoro.get().state(),
        "welcome": not config.get("shownWelcome", False),
        "lang": current_lang(),
        "i18n": {
            "start": tr("start"),
            "pause": tr("pause"),
            "resume": tr("resume"),
            "focus": tr("focus"),
            "break": tr("break_"),
            "idle": tr("pomodoro_idle"),
            "cards": tr("cards_unit"),
            "sessions": tr("sessions_today"),
            "welcome": tr("welcome_toast"),
            "mon": tr("mon"), "wed": tr("wed"), "fri": tr("fri"),
        },
        "months": [month_name(m) for m in range(1, 13)],
        "dayMonthFormat": day_month_format(),
    }

    body = (
        f'<div class="awd-shell mode-{sidebar_mode}" id="awd-shell">'
        + _sidebar_html(config, tree, due_total)
        + _sidebar_mini_html(config, tree)
        + '<div class="awd-main">'
        + _topline_html()
        + '<div class="awd" id="awd-root">'
        + "".join(sections)
        + "</div></div></div>"
        + '<div id="awd-tooltip" class="awd-tooltip" hidden></div>'
        + f'<script>window.AWD_DATA = {json.dumps(js_data)};</script>'
    )

    self.web.stdHtml(body=body, css=[], js=[], context=self)

    # Always redraw the bottom bar with the deck browser's own buttons —
    # otherwise it keeps whatever the previous screen left there (e.g. the
    # reviewer's answer bar), and Anki's mouse-driven auto-hide machinery can
    # re-show that stale bar over the dashboard.
    try:
        self._drawButtons()
    except Exception:
        pass
    apply_bar_visibility("deckBrowser")

    gui_hooks.deck_browser_did_render(self)
