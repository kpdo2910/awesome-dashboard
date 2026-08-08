"""First-run onboarding overlay.

Shown once, over the dashboard, before the add-on has any settings of its own.
It is plain HTML in the deck-browser webview rather than a Qt dialog: the
illustrations are SVG that reads the live palette, and the closing flourish
needs an animation Qt would make hard work of.

The overlay collects three choices, hands them to `awd:onboard:*` (ui/bridge.py)
and only lets the page re-render at the very end — a re-render mid-flow would
tear the overlay out from under the user.
"""

import html

from ..core import themes
from ..core.translations import tr


def _theme_card(key: str, palette: dict) -> str:
    """A theme swatch drawn from that theme's own colours, not the active one."""
    return f"""
    <button class="awd-ob-opt awd-ob-theme" data-choice="theme" data-value="{key}">
      <span class="awd-ob-swatch" style="background:{palette['bg']}">
        <i style="background:{palette['accent']}"></i>
        <i style="background:{palette['new']}"></i>
        <i style="background:{palette['due']}"></i>
      </span>
      <span class="awd-ob-opt-name">{html.escape(tr(f"theme_{key}").split("—")[0].strip())}</span>
    </button>"""


def _sidebar_art(mode: str) -> str:
    """Miniature of the dashboard layout in each sidebar mode."""
    rail = {"full": 26, "compact": 10, "hidden": 0}[mode]
    side = (
        f'<rect x="4" y="4" width="{rail}" height="52" rx="4" fill="currentColor"'
        ' opacity=".28"/>' if rail else ""
    )
    x = 4 + (rail + 4 if rail else 0)
    width = 88 - x
    rows = "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="7" rx="3" fill="currentColor"'
        f' opacity="{o}"/>'
        for y, w, o in ((8, width, ".5"), (20, width, ".22"), (31, width, ".22"),
                        (42, width * 0.6, ".22"))
    )
    return (
        '<svg viewBox="0 0 92 60" aria-hidden="true">'
        f'<rect x="1" y="1" width="90" height="58" rx="7" fill="none"'
        ' stroke="currentColor" stroke-opacity=".25"/>'
        f"{side}{rows}</svg>"
    )


def _skin_art(on: bool) -> str:
    """Answer side with the add-on's card design, versus the note's own."""
    if on:
        body = (
            '<rect x="14" y="10" width="64" height="40" rx="7" fill="currentColor"'
            ' opacity=".1"/>'
            '<rect x="22" y="17" width="22" height="6" rx="3" fill="currentColor"'
            ' opacity=".55"/>'
            '<rect x="22" y="28" width="48" height="4" rx="2" fill="currentColor"'
            ' opacity=".26"/>'
            '<rect x="22" y="36" width="36" height="4" rx="2" fill="currentColor"'
            ' opacity=".26"/>'
        )
    else:
        body = (
            '<rect x="18" y="20" width="56" height="5" rx="2" fill="currentColor"'
            ' opacity=".35"/>'
            '<rect x="18" y="30" width="40" height="5" rx="2" fill="currentColor"'
            ' opacity=".22"/>'
        )
    return (
        '<svg viewBox="0 0 92 60" aria-hidden="true">'
        '<rect x="1" y="1" width="90" height="58" rx="7" fill="none"'
        ' stroke="currentColor" stroke-opacity=".25"/>'
        f"{body}</svg>"
    )


def _appearance_art(mode: str) -> str:
    """Literal light and dark, not palette colours — the choice is about these."""
    faces = {
        "light": [("#ffffff", "#1d1d1f", 0, 90)],
        "dark": [("#1c1c1f", "#f5f5f7", 0, 90)],
        "system": [("#ffffff", "#1d1d1f", 0, 46), ("#1c1c1f", "#f5f5f7", 46, 44)],
    }[mode]
    parts = []
    for bg, fg, x, width in faces:
        parts.append(
            f'<rect x="{x + 1}" y="1" width="{width}" height="58" fill="{bg}"/>'
            f'<rect x="{x + 9}" y="16" width="{max(10, width - 22)}" height="6"'
            f' rx="3" fill="{fg}" opacity=".8"/>'
            f'<rect x="{x + 9}" y="28" width="{max(8, width - 34)}" height="5"'
            f' rx="2.5" fill="{fg}" opacity=".35"/>'
            f'<rect x="{x + 9}" y="38" width="{max(6, width - 46)}" height="5"'
            f' rx="2.5" fill="{fg}" opacity=".35"/>'
        )
    # Three of these live in the same document, so the clip needs its own id.
    clip = f"awdObClip-{mode}"
    return (
        '<svg viewBox="0 0 92 60" aria-hidden="true">'
        f'<clipPath id="{clip}"><rect x="1" y="1" width="90" height="58" rx="7"/>'
        "</clipPath>"
        f'<g clip-path="url(#{clip})">{"".join(parts)}</g>'
        '<rect x="1" y="1" width="90" height="58" rx="7" fill="none"'
        ' stroke="currentColor" stroke-opacity=".25"/></svg>'
    )


def _option(choice: str, value: str, art: str, name: str, sub: str = "") -> str:
    sub_html = f'<span class="awd-ob-opt-sub">{html.escape(sub)}</span>' if sub else ""
    return f"""
    <button class="awd-ob-opt" data-choice="{choice}" data-value="{value}">
      <span class="awd-ob-art">{art}</span>
      <span class="awd-ob-opt-name">{html.escape(name)}</span>
      {sub_html}
    </button>"""


def overlay_html() -> str:
    theme_cards = "".join(
        _theme_card(key, themes.THEMES[key]["light"])
        for key in ("glass", "terracotta", "matcha", "ajisai", "sakura", "sumi")
        if key in themes.THEMES
    )
    sidebar_options = "".join(
        _option("sidebarMode", mode, _sidebar_art(mode), tr(f"sidebar_{mode}"))
        for mode in ("full", "compact", "hidden")
    )
    appearance_options = "".join(
        _option("appearance", mode, _appearance_art(mode), tr(f"appearance_{mode}"))
        for mode in ("light", "dark", "system")
    )
    skin_options = (
        _option("cardSkinDefault", "1", _skin_art(True),
                tr("ob_skin_on"), tr("ob_skin_on_sub"))
        + _option("cardSkinDefault", "0", _skin_art(False),
                  tr("ob_skin_off"), tr("ob_skin_off_sub"))
    )
    bullets = "".join(
        f'<li>{html.escape(tr(key))}</li>'
        for key in ("ob_feat_1", "ob_feat_2", "ob_feat_3")
    )

    return f"""
<div class="awd-ob" id="awd-ob" hidden>
  <div class="awd-ob-sheet" id="awd-ob-sheet">

    <div class="awd-ob-top" id="awd-ob-top" hidden>
      <button class="awd-ob-nav" data-back="1">{html.escape(tr("ob_back"))}</button>
      <button class="awd-ob-nav" data-skip="1">{html.escape(tr("ob_skip"))}</button>
    </div>

    <section class="awd-ob-step" data-step="0">
      <div class="awd-ob-mark">◈</div>
      <h1 class="awd-ob-title">Awesome Dashboard</h1>
      <p class="awd-ob-sub">{html.escape(tr("ob_intro_sub"))}</p>
      <ul class="awd-ob-feats">{bullets}</ul>
      <div class="awd-ob-foot stack">
        <button class="awd-ob-go" data-go="1">{html.escape(tr("ob_start"))}</button>
        <button class="awd-ob-skip" data-skip="1">{html.escape(tr("ob_skip"))}</button>
      </div>
    </section>

    <section class="awd-ob-step" data-step="1" hidden>
      <h2 class="awd-ob-h">{html.escape(tr("ob_theme_title"))}</h2>
      <p class="awd-ob-sub">{html.escape(tr("ob_theme_sub"))}</p>
      <div class="awd-ob-grid themes">{theme_cards}</div>
      <div class="awd-ob-foot">
        <button class="awd-ob-go" data-go="2">{html.escape(tr("ob_next"))}</button>
      </div>
    </section>

    <section class="awd-ob-step" data-step="2" hidden>
      <h2 class="awd-ob-h">{html.escape(tr("ob_look_title"))}</h2>
      <p class="awd-ob-sub">{html.escape(tr("ob_look_sub"))}</p>
      <div class="awd-ob-grid">{appearance_options}</div>
      <div class="awd-ob-foot">
        <button class="awd-ob-go" data-go="3">{html.escape(tr("ob_next"))}</button>
      </div>
    </section>

    <section class="awd-ob-step" data-step="3" hidden>
      <h2 class="awd-ob-h">{html.escape(tr("ob_sidebar_title"))}</h2>
      <p class="awd-ob-sub">{html.escape(tr("ob_sidebar_sub"))}</p>
      <div class="awd-ob-grid">{sidebar_options}</div>
      <div class="awd-ob-foot">
        <button class="awd-ob-go" data-go="4">{html.escape(tr("ob_next"))}</button>
      </div>
    </section>

    <section class="awd-ob-step" data-step="4" hidden>
      <h2 class="awd-ob-h">{html.escape(tr("ob_skin_title"))}</h2>
      <p class="awd-ob-sub">{html.escape(tr("ob_skin_sub"))}</p>
      <div class="awd-ob-grid two">{skin_options}</div>
      <div class="awd-ob-foot">
        <button class="awd-ob-go awd-ob-apply" data-apply="1">
          {html.escape(tr("ob_apply"))}
        </button>
      </div>
    </section>

    <section class="awd-ob-step awd-ob-center" data-step="5" hidden>
      <div class="awd-ob-spinner" aria-hidden="true"><i></i><i></i><i></i></div>
      <p class="awd-ob-loading" id="awd-ob-loading">{html.escape(tr("ob_applying"))}</p>
    </section>

    <section class="awd-ob-step awd-ob-center" data-step="6" hidden>
      <div class="awd-ob-script"><span>Awesome Dashboard</span></div>
      <p class="awd-ob-sub">{html.escape(tr("ob_ready_sub"))}</p>
      <div class="awd-ob-foot">
        <button class="awd-ob-go" data-finish="1">{html.escape(tr("ob_finish"))}</button>
      </div>
    </section>

    <div class="awd-ob-dots" id="awd-ob-dots" aria-hidden="true"></div>
  </div>
</div>
"""
