"""Theme Anki's other screens to match the active palette.

Webviews (editor, Stats, deck options, dialogs) get Anki's own CSS custom
properties overridden via webview_will_set_content — the reviewer card webview
is excluded so note templates render untouched. Qt chrome (window backgrounds,
inputs, selections) gets a rebuilt QPalette, which needs a restart to revert.
"""

import math
import os
import re

from aqt import mw

from ..core import conf, paths, themes


# --- color math ---------------------------------------------------------------

def _parse_color(value: str):
    value = (value or "").strip()
    m = re.match(r"#([0-9a-fA-F]{6})$", value)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    m = re.match(r"#([0-9a-fA-F]{3})$", value)
    if m:
        h = m.group(1)
        return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0
    m = re.match(r"rgba?\(([^)]+)\)", value)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return r, g, b, a
    return 255, 255, 255, 1.0


def flatten(color: str, behind: str) -> str:
    """Alpha-composite `color` over `behind`, returning an opaque hex color."""
    r, g, b, a = _parse_color(color)
    br, bgc, bb, _ = _parse_color(behind)
    if a >= 1.0:
        return "#%02x%02x%02x" % (round(r), round(g), round(b))
    return "#%02x%02x%02x" % (
        round(r * a + br * (1 - a)),
        round(g * a + bgc * (1 - a)),
        round(b * a + bb * (1 - a)),
    )


def qss_accent(pal: dict, bg: str) -> str:
    """The accent as a QSS brush — a gradient when the theme has one.

    Qt has no `linear-gradient`, so the CSS value is re-expressed as
    `qlineargradient`, whose control points are fractions of the widget box
    rather than an angle.
    """
    parsed = themes.parse_gradient(pal.get("accent-grad", ""))
    if not parsed:
        return flatten(pal["accent"], bg)
    start, end, angle = parsed
    # CSS angles run clockwise from "to top"; y grows downward on screen.
    radians = math.radians(angle)
    dx, dy = math.sin(radians), -math.cos(radians)
    return (
        f"qlineargradient(x1:{0.5 - dx / 2:.3f}, y1:{0.5 - dy / 2:.3f},"
        f" x2:{0.5 + dx / 2:.3f}, y2:{0.5 + dy / 2:.3f},"
        f" stop:0 {flatten(start, bg)}, stop:1 {flatten(end, bg)})"
    )


# --- webview CSS variable overrides ---------------------------------------------

def vars_mapping(theme_name: str, night: bool) -> dict:
    pal = themes.palette(theme_name, night)
    bg = pal["bg"]
    surface = flatten(pal["surface"], bg)
    inset = flatten(pal["inset"], bg)
    border = flatten(pal["border"], bg)
    subtle = flatten(pal["subtle"], bg)
    accent = pal["accent"]

    mapping = {
        "canvas": bg,
        "canvas-elevated": surface,
        "canvas-elevated-hover": inset,
        "canvas-inset": inset,
        "canvas-overlay": surface,
        "canvas-glass": pal["surface"],
        "canvas-code": inset,
        "fg": pal["text"],
        "fg-subtle": pal["subtle"],
        "fg-faint": pal["faint"],
        "fg-disabled": pal["faint"],
        "fg-link": accent,
        "border": border,
        "border-subtle": border,
        "border-strong": subtle,
        "border-focus": accent,
        "focus-color": accent,
        "button-bg": inset,
        "button-gradient-start": surface,
        "button-gradient-end": inset,
        "button-hover-border": subtle,
        "button-primary-bg": accent,
        "button-primary-gradient-start": accent,
        "button-primary-gradient-end": accent,
        "highlight-bg": pal["accent-soft"],
        "highlight-fg": pal["text"],
        "selected-bg": pal["accent-soft"],
        "selected-fg": pal["text"],
        "scrollbar-bg": inset,
        "scrollbar-bg-hover": border,
        "scrollbar-bg-active": subtle,
        "state-new": pal["new"],
        "state-learn": pal["learn"],
        "state-review": pal["due"],
    }
    return {f"--{key}": value for key, value in mapping.items()}


def anki_vars_css(theme_name: str, night: bool) -> str:
    mapping = vars_mapping(theme_name, night)
    body = "; ".join(f"{key}: {value}" for key, value in mapping.items())
    return (
        '<style id="awd-anki-vars">'
        f":root, :root.night-mode {{ {body}; }}"
        "</style>"
    )


# --- Qt application palette ------------------------------------------------------

def install_sveltekit_hook() -> None:
    """Theme the SvelteKit pages (Stats, Deck Options, Congrats).

    They bypass webview_will_set_content and set their colours inline on <html>, so
    their loader is wrapped and the values re-applied after load to outlive
    hydration — inline style is Anki's own mechanism, so the last writer wins.
    """
    from aqt.webview import AnkiWebView

    if getattr(AnkiWebView, "_awd_sveltekit_wrapped", False):
        return
    # Anki builds older than the SvelteKit page loader have nothing to wrap.
    # This runs at import time, so reading the attribute directly would raise
    # AttributeError and take the whole add-on down with it.
    original = getattr(AnkiWebView, "load_sveltekit_page", None)
    if original is None:
        return

    def wrapped(self, path, *args, **kwargs):
        result = original(self, path, *args, **kwargs)
        try:
            config = conf.get()
            if config.get("styleSystemScreens", True):
                import json

                from aqt.theme import theme_manager

                mapping = vars_mapping(
                    config.get("theme", "glass"), theme_manager.night_mode
                )
                js = (
                    "(function(){var vars=" + json.dumps(mapping) + ";"
                    "function apply(){var root=document.documentElement;"
                    "for (var key in vars) root.style.setProperty(key, vars[key]);}"
                    "apply(); setTimeout(apply, 300);"
                    "setTimeout(apply, 800); setTimeout(apply, 1600);})();"
                )

                def inject(ok, web=self, code=js):
                    try:
                        web.loadFinished.disconnect(inject)
                    except Exception:
                        pass
                    if ok:
                        web.eval(code)

                self.loadFinished.connect(inject)
        except Exception as e:
            print(f"[Awesome Dashboard] sveltekit theming failed: {e}")
        return result

    AnkiWebView.load_sveltekit_page = wrapped
    AnkiWebView._awd_sveltekit_wrapped = True


def _live_webviews():
    """Every webview of ours that may be showing right now."""
    candidates = (
        getattr(getattr(mw, "deckBrowser", None), "web", None),
        getattr(getattr(mw, "overview", None), "web", None),
        getattr(getattr(mw, "reviewer", None), "web", None),
        getattr(mw, "toolbarWeb", None),
        getattr(mw, "bottomWeb", None),
    )
    return [web for web in candidates if web is not None]


def animate_theme_change() -> None:
    """Cross-fade the live pages into the current palette.

    Re-rendering would cut hard and lose scroll position; pushing the CSS variables
    into open pages lets `theme.css` transition them instead.
    """
    import json

    try:
        from aqt.theme import theme_manager

        night = theme_manager.night_mode
    except Exception:
        night = False

    config = conf.get()
    theme_name = config.get("theme", "glass")
    variables = dict(themes.variables(theme_name, night))
    if config.get("styleSystemScreens", True):
        # Anki's own variables ride along so editor chrome fades in step.
        variables.update(vars_mapping(theme_name, night))

    script = (
        "typeof AwdTheme !== 'undefined' && AwdTheme.apply("
        f"{json.dumps(variables)});"
    )
    for web in _live_webviews():
        try:
            web.eval(script)
        except Exception:
            pass


def apply_app_palette() -> None:
    """Recolor the Qt palette so dialog chrome matches the theme."""
    config = conf.get()
    if not config.get("styleSystemScreens", True):
        return
    try:
        from aqt.qt import QColor, QPalette
        from aqt.theme import theme_manager

        pal = themes.palette(config.get("theme", "glass"), theme_manager.night_mode)
        bg = pal["bg"]

        def qc(value, behind=bg):
            return QColor(flatten(value, behind))

        palette = mw.app.palette()
        roles = QPalette.ColorRole
        palette.setColor(roles.Window, qc(bg))
        palette.setColor(roles.WindowText, qc(pal["text"]))
        palette.setColor(roles.Base, qc(pal["surface"]))
        palette.setColor(roles.AlternateBase, qc(pal["inset"]))
        palette.setColor(roles.Text, qc(pal["text"]))
        palette.setColor(roles.Button, qc(pal["inset"]))
        palette.setColor(roles.ButtonText, qc(pal["text"]))
        palette.setColor(roles.Highlight, qc(pal["accent"]))
        palette.setColor(
            roles.HighlightedText, qc(pal.get("on-accent", "#ffffff"), pal["accent"])
        )
        palette.setColor(roles.Link, qc(pal["accent"]))
        palette.setColor(roles.PlaceholderText, qc(pal["faint"]))
        palette.setColor(roles.ToolTipBase, qc(pal["surface"]))
        palette.setColor(roles.ToolTipText, qc(pal["text"]))
        mw.app.setPalette(palette)
    except Exception as e:
        print(f"[Awesome Dashboard] app palette failed: {e}")


def _icons_dir() -> str:
    """Generated QSS assets live in the add-on's persistent user_files."""
    return paths.user_files("qt_icons")


def _chevron_svg(direction: str, color: str) -> str:
    """Write a small chevron SVG for QSS arrows; returns a url()-safe path."""
    outlines = {
        "up": "M2.5 6.3 5 3.8 7.5 6.3",
        "down": "M2.5 3.7 5 6.2 7.5 3.7",
        "left": "M6.3 2.5 3.8 5 6.3 7.5",
        "right": "M3.7 2.5 6.2 5 3.7 7.5",
    }
    slug = re.sub(r"[^0-9a-zA-Z]", "", color)
    file_path = os.path.join(_icons_dir(), f"chev_{direction}_{slug}.svg")
    if not os.path.exists(file_path):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"'
            f' viewBox="0 0 10 10"><path d="{outlines[direction]}" fill="none"'
            f' stroke="{color}" stroke-width="1.6" stroke-linecap="round"'
            ' stroke-linejoin="round"/></svg>'
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg)
    return file_path.replace(os.sep, "/")


def _switch_svg(on: bool, accent: str, track_off: str) -> str:
    """macOS-style toggle switch image for QCheckBox indicators."""
    track = accent if on else track_off
    knob_x = 26 if on else 12
    slug = re.sub(r"[^0-9a-zA-Z]", "", f"{'on' if on else 'off'}{track}")
    file_path = os.path.join(_icons_dir(), f"switch_{slug}.svg")
    if not os.path.exists(file_path):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="38" height="24"'
            ' viewBox="0 0 38 24">'
            f'<rect x="0.5" y="0.5" width="37" height="23" rx="11.5" fill="{track}"/>'
            f'<circle cx="{knob_x}" cy="12" r="10" fill="#ffffff"'
            ' stroke="rgba(0,0,0,0.06)"/>'
            "</svg>"
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg)
    return file_path.replace(os.sep, "/")


def _radio_svg(on: bool, accent: str, border: str, surface: str, dot: str) -> str:
    """macOS-style radio image for QRadioButton indicators."""
    slug = re.sub(
        r"[^0-9a-zA-Z]", "", f"{'on' if on else 'off'}{accent}{border}{surface}"
    )
    file_path = os.path.join(_icons_dir(), f"radio_{slug}.svg")
    if not os.path.exists(file_path):
        head = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"'
            ' viewBox="0 0 20 20">'
        )
        if on:
            svg = (
                f'{head}<circle cx="10" cy="10" r="9" fill="{accent}"/>'
                f'<circle cx="10" cy="10" r="3.2" fill="{dot}"/></svg>'
            )
        else:
            svg = (
                f'{head}<circle cx="10" cy="10" r="8.5" fill="{surface}"'
                f' stroke="{border}"/></svg>'
            )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg)
    return file_path.replace(os.sep, "/")


def nav_icon(kind: str, color: str) -> str:
    """Colored rounded-square nav icon (macOS System Settings style)."""
    glyphs = {
        "general": (
            '<path d="M6 8.2h11M6 11.5h11M6 14.8h11" stroke="#fff"'
            ' stroke-width="1.7" stroke-linecap="round" fill="none"/>'
        ),
        "look": (
            '<circle cx="11.5" cy="11.5" r="5.4" fill="none" stroke="#fff"'
            ' stroke-width="1.5"/>'
            '<path d="M11.5 6.1a5.4 5.4 0 0 1 0 10.8z" fill="#fff"/>'
        ),
        "about": (
            '<circle cx="11.5" cy="11.5" r="6.4" fill="none" stroke="#fff"'
            ' stroke-width="1.5"/>'
            '<path d="M11.5 10.3v4.6" stroke="#fff" stroke-width="1.7"'
            ' stroke-linecap="round"/>'
            '<circle cx="11.5" cy="8.1" r="1" fill="#fff"/>'
        ),
        "events": (
            '<rect x="5.2" y="6.4" width="12.6" height="10.8" rx="2.2"'
            ' fill="none" stroke="#fff" stroke-width="1.5"/>'
            '<path d="M5.2 10h12.6" stroke="#fff" stroke-width="1.5"/>'
            '<path d="M8.8 4.8v2.3M14.2 4.8v2.3" stroke="#fff"'
            ' stroke-width="1.5" stroke-linecap="round"/>'
        ),
        # rising memory curve
        "fsrs": (
            '<path d="M5 16.6c3.4 0 4.6-8.6 12.6-10.2" fill="none" stroke="#fff"'
            ' stroke-width="1.6" stroke-linecap="round"/>'
            '<circle cx="17.4" cy="6.3" r="1.9" fill="#fff"/>'
            '<path d="M5 4.9v13.2h13.4" fill="none" stroke="#fff"'
            ' stroke-width="1.4" stroke-linecap="round" opacity="0.55"/>'
        ),
        # stacked cards — distinct from the "general" hamburger at a glance
        "decks": (
            '<rect x="7.4" y="4.6" width="10.4" height="7" rx="1.8"'
            ' fill="none" stroke="#fff" stroke-width="1.4"/>'
            '<path d="M5.4 8.2v8.6a1.8 1.8 0 0 0 1.8 1.8h8.2" fill="none"'
            ' stroke="#fff" stroke-width="1.4" stroke-linecap="round"/>'
        ),
    }
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="23" height="23"'
        ' viewBox="0 0 23 23">'
        f'<rect x="0.5" y="0.5" width="22" height="22" rx="6" fill="{color}"/>'
        f"{glyphs.get(kind, glyphs['general'])}"
        "</svg>"
    )
    # The cache key hashes the artwork, not just the name — otherwise editing a
    # glyph leaves the old file on disk and the icon never changes.
    import hashlib

    digest = hashlib.md5(svg.encode()).hexdigest()[:8]
    slug = re.sub(r"[^0-9a-zA-Z]", "", kind)
    file_path = os.path.join(_icons_dir(), f"nav_{slug}_{digest}.svg")
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg)
    return file_path.replace(os.sep, "/")


def settings_dialog_qss() -> str:
    """QSS for the add-on's own settings dialog, matched to the palette."""
    try:
        from aqt.theme import theme_manager

        night = theme_manager.night_mode
    except Exception:
        night = False
    config = conf.get()
    pal = themes.palette(config.get("theme", "glass"), night)
    bg = pal["bg"]
    surface = flatten(pal["surface"], bg)
    inset = flatten(pal["inset"], bg)
    border = flatten(pal["border"], bg)
    text = flatten(pal["text"], bg)
    accent = flatten(pal["accent"], bg)
    # Solid for switches and SVG fills, which take a colour; the brush is only
    # for the QSS surfaces big enough to show a gradient.
    accent_brush = qss_accent(pal, bg)
    soft = flatten(pal["accent-soft"], bg)
    on_accent = flatten(pal.get("on-accent", "#ffffff"), accent)
    subtle = flatten(pal["subtle"], bg)
    faint = flatten(pal["faint"], bg)
    seg_sel = "#636369" if night else "#ffffff"
    scroll_thumb = (
        "rgba(255, 255, 255, 0.28)" if night else "rgba(0, 0, 0, 0.26)"
    )
    scroll_thumb_hover = (
        "rgba(255, 255, 255, 0.45)" if night else "rgba(0, 0, 0, 0.42)"
    )
    up = _chevron_svg("up", subtle)
    down = _chevron_svg("down", subtle)
    left = _chevron_svg("left", subtle)
    right = _chevron_svg("right", subtle)
    switch_on = _switch_svg(True, accent, border)
    switch_off = _switch_svg(False, accent, border)

    return f"""
    QDialog {{ background: {bg}; }}
    QLabel {{ color: {text}; background: transparent; }}

    /* --- System Settings layout: left nav + grouped inset cards --- */
    QWidget#awdNav {{
        background: {inset};
        border-right: 1px solid {border};
    }}
    QPushButton#awdNavBtn {{
        background: transparent;
        border: none;
        border-radius: 8px;
        /* The margin is what keeps the hover/selection pills from touching —
           layout spacing alone leaves the painted rects nearly flush. */
        margin: 3px 0;
        padding: 7px 9px;
        text-align: left;
        font-size: 13px;
        font-weight: 600;
        color: {text};
    }}
    /* No hover state: only the selected page is tinted, so the nav reads as
       one clear indicator instead of two competing highlights. */
    QPushButton#awdNavBtn:checked {{
        background: {accent_brush};
        color: {on_accent};
    }}
    QLabel#awdPageTitle {{
        font-size: 14px;
        font-weight: 700;
        padding: 0 20px;
        border-bottom: 1px solid {border};
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    /* macOS overlay scrollbars: no arrows, no trough, thin rounded thumb */
    QScrollBar:vertical {{
        background: transparent;
        width: 11px;
        margin: 2px 1px 2px 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 11px;
        margin: 0 2px 1px 2px;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: {scroll_thumb};
        border-radius: 4px;
        border: 2px solid transparent;
        background-clip: padding;
    }}
    QScrollBar::handle:vertical {{ min-height: 32px; }}
    QScrollBar::handle:horizontal {{ min-width: 32px; }}
    QScrollBar::handle:hover {{ background: {scroll_thumb_hover}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        width: 0; height: 0; border: none; background: none;
    }}
    QScrollBar::up-arrow, QScrollBar::down-arrow,
    QScrollBar::left-arrow, QScrollBar::right-arrow {{
        width: 0; height: 0; background: none;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QWidget#awdGroup {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 11px;
    }}
    QFrame#awdSep {{
        background: {border};
        border: none;
        margin-left: 14px;
    }}
    QLabel#awdRowTitle {{ font-size: 13px; font-weight: 600; }}
    QLabel#awdRowSub {{ font-size: 11px; color: {subtle}; }}
    QLabel#awdSection {{
        font-size: 10.5px;
        font-weight: 700;
        letter-spacing: 1px;
        color: {subtle};
    }}
    QWidget#awdGroup QLineEdit,
    QWidget#awdGroup QSpinBox,
    QWidget#awdGroup QDateEdit,
    QWidget#awdGroup QComboBox {{ background: {inset}; }}
    QWidget#awdSeg {{ background: {inset}; border-radius: 8px; }}
    QPushButton#awdSegBtn {{
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 600;
        color: {text};
        min-width: 0;
    }}
    QPushButton#awdSegBtn:checked {{ background: {seg_sel}; }}
    QWidget#awdFootBar {{
        background: {bg};
        border-top: 1px solid {border};
    }}

    /* macOS-style switches */
    QCheckBox {{ color: {text}; spacing: 0px; }}
    QCheckBox::indicator {{ width: 38px; height: 24px; }}
    QCheckBox::indicator:unchecked {{ image: url("{switch_off}"); }}
    QCheckBox::indicator:checked {{ image: url("{switch_on}"); }}
    QLineEdit, QSpinBox, QDateEdit, QComboBox, QListWidget {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 4px 8px;
        selection-background-color: {soft};
        selection-color: {text};
    }}
    QSpinBox, QDateEdit {{ min-height: 24px; padding-right: 2px; }}

    QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 20px;
        background: {inset};
        border-left: 1px solid {border};
        border-top-right-radius: 7px;
        margin: 1px 1px 0 0;
    }}
    QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 20px;
        background: {inset};
        border-left: 1px solid {border};
        border-bottom-right-radius: 7px;
        margin: 0 1px 1px 0;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {border}; }}
    QSpinBox::up-arrow {{ image: url("{up}"); width: 9px; height: 9px; }}
    QSpinBox::down-arrow {{ image: url("{down}"); width: 9px; height: 9px; }}

    QDateEdit::drop-down, QComboBox::drop-down {{
        subcontrol-origin: border;
        subcontrol-position: center right;
        width: 24px;
        border: none;
    }}
    QDateEdit::down-arrow, QComboBox::down-arrow {{
        image: url("{down}");
        width: 10px;
        height: 10px;
    }}

    QCalendarWidget {{ background: {surface}; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background: {surface};
        border-bottom: 1px solid {border};
    }}
    QCalendarWidget QToolButton {{
        color: {text};
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 5px 10px;
        font-weight: 600;
    }}
    QCalendarWidget QToolButton:hover {{ background: {soft}; }}
    QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
    QCalendarWidget QToolButton#qt_calendar_prevmonth {{
        qproperty-icon: url("{left}");
    }}
    QCalendarWidget QToolButton#qt_calendar_nextmonth {{
        qproperty-icon: url("{right}");
    }}
    QCalendarWidget QMenu {{ background: {surface}; color: {text}; }}
    QCalendarWidget QAbstractItemView:enabled {{
        background: {surface};
        color: {text};
        selection-background-color: {accent};
        selection-color: {on_accent};
        outline: none;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {flatten(pal["faint"], bg)}; }}

    QListWidget::item {{ padding: 5px 6px; border-bottom: 1px solid {border}; }}
    QListWidget::item:selected {{ background: {soft}; color: {text}; border-radius: 6px; }}

    /* events list + attached +/- footer, System Settings style */
    QListWidget#awdEventsList {{
        background: {surface};
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        border-bottom: none;
        padding: 3px 4px;
    }}
    QListWidget#awdEventsList::item {{
        padding: 4px 8px;
        border-bottom: none;
        border-radius: 6px;
    }}
    QWidget#awdListFooter {{
        background: {surface};
        border: 1px solid {border};
        border-top: 1px solid {border};
        border-bottom-left-radius: 8px;
        border-bottom-right-radius: 8px;
    }}
    QPushButton#awdMini {{
        background: transparent;
        border: none;
        border-radius: 5px;
        min-width: 26px;
        max-width: 26px;
        min-height: 20px;
        max-height: 20px;
        padding: 0;
        font-size: 15px;
        font-weight: 600;
        color: {subtle};
    }}
    QPushButton#awdMini:hover {{ background: {inset}; }}
    QPushButton#awdMini:pressed {{ background: {border}; }}
    QPushButton {{
        background: {inset};
        color: {text};
        border: 1px solid {border};
        border-radius: 14px;
        padding: 6px 18px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {border}; }}
    QPushButton:default {{
        background: {accent_brush};
        color: {on_accent};
        border: none;
    }}
    QPushButton#awdPrimary {{
        background: {accent_brush};
        color: {on_accent};
        border: none;
    }}
    QPushButton#awdPrimary:hover {{ background: {accent_brush}; }}
    QPushButton#awdDanger {{ color: #FF3B30; }}
    QPushButton#awdDanger:hover {{
        background: rgba(255, 59, 48, 0.16);
        border-color: rgba(255, 59, 48, 0.35);
    }}
    """


def custom_study_qss() -> str:
    """Anki's Custom Study dialog, matched to the add-on's own dialogs.

    Anki builds that dialog from its own .ui form, so this rides on the settings
    QSS — same palette, same controls — and only adds the radio buttons, which
    the add-on's own dialogs never use.
    """
    try:
        from aqt.theme import theme_manager

        night = theme_manager.night_mode
    except Exception:
        night = False
    pal = themes.palette(conf.get().get("theme", "glass"), night)
    bg = pal["bg"]
    text = flatten(pal["text"], bg)
    accent = flatten(pal["accent"], bg)
    border = flatten(pal["border"], bg)
    surface = flatten(pal["surface"], bg)
    subtle = flatten(pal["subtle"], bg)
    dot = flatten(pal.get("on-accent", "#ffffff"), accent)
    radio_on = _radio_svg(True, accent, border, surface, dot)
    radio_off = _radio_svg(False, accent, border, surface, dot)

    return settings_dialog_qss() + f"""
    QRadioButton {{
        color: {text};
        spacing: 9px;
        padding: 4px 0;
        font-size: 13px;
    }}
    QRadioButton::indicator {{ width: 20px; height: 20px; }}
    QRadioButton::indicator:unchecked {{ image: url("{radio_off}"); }}
    QRadioButton::indicator:checked {{ image: url("{radio_on}"); }}

    /* Qt reserves the top edge of a group box for its title, so the card needs
       its own padding and the title needs to sit clear of the border. */
    QGroupBox#awdGroup {{ padding: 12px 14px; margin-top: 6px; }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 4px;
        color: {subtle};
        font-size: 12px;
        font-weight: 600;
    }}
    """


def _style_custom_study(dialog) -> None:
    from aqt.qt import QGroupBox

    # Anki's form wraps the spinner row in a QGroupBox; renaming it makes it pick
    # up the same inset-card styling the add-on's own grouped rows use.
    for box in dialog.findChildren(QGroupBox):
        box.setObjectName("awdGroup")
    dialog.setStyleSheet(custom_study_qss())


def install_custom_study_hook() -> None:
    """Restyle Anki's Custom Study dialog before it is ever shown.

    It is the one native dialog the redesigned overview opens directly, so
    leaving it unthemed makes the theme look like it stops at the window edge.

    The hook goes on the generated form's setupUi rather than on
    CustomStudy.__init__: __init__ shows the dialog itself, so styling after it
    returns means the default look is painted first and the restyle lands as a
    visible flicker and resize. setupUi runs while the widgets are still being
    built, so the first frame drawn is already themed.
    """
    from aqt.forms import customstudy as custom_study_form

    form_cls = getattr(custom_study_form, "Ui_Dialog", None)
    if form_cls is None or getattr(form_cls, "_awd_styled", False):
        return
    original = form_cls.setupUi

    def wrapped(self, dialog):
        original(self, dialog)
        try:
            _style_custom_study(dialog)
        except Exception as e:
            print(f"[Awesome Dashboard] custom study theming failed: {e}")

    form_cls.setupUi = wrapped
    form_cls._awd_styled = True
