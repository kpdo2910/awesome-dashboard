"""Awesome Dashboard — a modern dashboard and screen redesign for Anki.

Wiring only: installs the screen renderers and registers the gui_hooks.

    core/      config, palettes, strings, collection statistics
    screens/   dashboard, deck overview, reviewer chrome, card skin, habits
    features/  Pomodoro timer, FSRS controls, habit tracker
    ui/        settings dialog, Qt/app theming, pycmd router, habit dialogs
"""

import os

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.reviewer import Reviewer
from aqt.toolbar import BottomBar, Toolbar

try:
    # Anki passes these wrapper objects (not Toolbar itself) as the
    # webview_will_set_content context for the top/bottom bars.
    from aqt.toolbar import BottomToolbar, TopToolbar
except ImportError:
    TopToolbar = BottomToolbar = None

from .core import background, conf, stats, themes
from .features.habits import store as habit_store
from .screens import card_skin, dashboard, overview, reviewer
from .ui import bridge, qt_theme

TOOLBAR_CONTEXTS = tuple(
    cls for cls in (Toolbar, BottomBar, TopToolbar, BottomToolbar) if cls is not None
)

addon_path = os.path.dirname(__file__)
addon_package = mw.addonManager.addonFromModule(__name__)
addon_root = f"/_addons/{addon_package}"
web_root = f"{addon_root}/web"

# Anki fullmatches this against the path below the add-on folder. user_files is
# exported too, so a background image the user picked can be served from there.
mw.addonManager.setWebExports(__name__, r"(web|user_files)/.*")

# Install our renderers before the first deck browser / overview render.
DeckBrowser._renderPage = dashboard.render_page
overview.install()
reviewer.install()

# Sveltekit pages (Stats, Deck Options, ...) need their own injection path.
qt_theme.install_sveltekit_hook()

# Custom Study is opened straight from the redesigned overview, so it gets the
# same treatment as the add-on's own dialogs.
qt_theme.install_custom_study_hook()

# Space on a skinned answer flips the card instead of rating it.
card_skin.install_space_toggle()

# Habit ticks are written behind a debounce, so every way out of a profile has
# to flush. Registering the hooks is safe here; nothing reads mw.col yet.
habit_store.install_hooks()


def _asset(*parts: str) -> str:
    """Web URL for an asset under web/, cache-busted by mtime."""
    try:
        version = int(os.path.getmtime(os.path.join(addon_path, "web", *parts)))
    except OSError:
        version = 0
    return f"{web_root}/{'/'.join(parts)}?v={version}"


def _css(*parts: str) -> str:
    return f'<link rel="stylesheet" href="{_asset(*parts)}">'


def _js(*parts: str) -> str:
    return f'<script src="{_asset(*parts)}"></script>'


def _add_classes(*names: str) -> str:
    joined = ", ".join(f"'{name}'" for name in names)
    return f"<script>document.documentElement.classList.add({joined});</script>"


def _theme_shell(theme_vars: str) -> str:
    """Palette variables plus the machinery that cross-fades between them."""
    return theme_vars + _css("shared", "theme.css") + _js("shared", "theme.js")


def _background_layer(config: dict) -> str:
    """The image layer and the translucent blocks — either, both, or neither.

    They are independent: an image can sit behind opaque cards, and cards can be
    translucent over the plain theme background with no image at all.
    """
    url = background.css_url(addon_root)
    opacity = max(0, min(100, int(config.get("cardOpacity", 100))))
    has_image = url != "none"
    soft_cards = opacity < 100
    if not has_image and not soft_cards:
        return ""

    variables = []
    classes = []
    if has_image:
        variables.append(f"--awd-bg-image: {url};")
        classes.append("awd-bgimg")
    if soft_cards:
        blur = max(0, min(40, int(config.get("cardBlur", 18))))
        # `none` rather than blur(0px): a zero blur still costs a compositing
        # layer, and the point of turning it off is to leave what is behind
        # sharp enough to actually make out.
        filter_value = f"blur({blur}px) saturate(160%)" if blur else "none"
        variables.append(
            f"--awd-card-mix: {opacity}%; --awd-card-filter: {filter_value};"
        )
        classes.append("awd-softcards")

    return (
        f'<style id="awd-bg-vars">:root {{ {" ".join(variables)} }}</style>'
        + _css("shared", "background.css")
        + _add_classes(*classes)
    )


def _night_mode() -> bool:
    try:
        from aqt.theme import theme_manager
        return bool(theme_manager.night_mode)
    except Exception:
        return False


def on_webview_will_set_content(web_content, context) -> None:
    config = conf.get()
    night = _night_mode()
    theme_vars = themes.css_variables(config.get("theme", "glass"), night)

    # Recolor Anki's own variables everywhere except the reviewer card
    # webview, so editor/stats/dialog pages follow the theme while note
    # templates keep rendering untouched.
    if config.get("styleSystemScreens", True) and not isinstance(context, Reviewer):
        web_content.head += qt_theme.anki_vars_css(config.get("theme", "glass"), night)

    if isinstance(context, DeckBrowser):
        web_content.head += _theme_shell(theme_vars)
        web_content.head += _css("shared", "heatmap.css")
        web_content.head += _css("dashboard", "dashboard.css")
        if config.get("showHabits", True):
            web_content.head += _css("shared", "loading.css")
            web_content.head += _css("shared", "switch.css")
            web_content.head += _css("habits", "habits.css")
        web_content.head += _background_layer(config)
        # heatmap.js before dashboard.js: the activity grid is built from it.
        web_content.head += _js("shared", "heatmap.js")
        web_content.head += _js("dashboard", "dashboard.js")
        if config.get("showHabits", True):
            web_content.head += _js("habits", "habits.js")
            # The report is an overlay in this same page, not a webview of its
            # own — see screens/habit_report.py.
            web_content.head += _js("habits", "report.js")
        if not config.get("shownWelcome", False):
            web_content.head += _css("shared", "loading.css")
            web_content.head += _css("dashboard", "onboarding.css")
            web_content.head += _js("dashboard", "onboarding.js")
    elif isinstance(context, Overview):
        if config.get("styleOverview", True):
            web_content.head += _theme_shell(theme_vars)
            web_content.head += _add_classes("awd-overview")
            web_content.head += _css("overview", "overview.css")
            web_content.head += _background_layer(config)
    elif isinstance(context, Reviewer):
        # Theme vars + the per-deck card-skin stylesheet are always available;
        # the skin only activates for decks the user opted in (card_skin.py).
        web_content.head += _theme_shell(theme_vars)
        web_content.head += _css("reviewer", "card_skin.css")
        web_content.head += _js("reviewer", "card_skin.js")
        if config.get("styleReviewer", True):
            web_content.head += _add_classes("awd-reviewer", "awd-rev-chrome")
            web_content.head += _css("reviewer", "backdrop.css")
            web_content.head += _css("reviewer", "chrome.css")
            web_content.head += _js("reviewer", "chrome.js")
            # Our own header/answer bar, replacing the native ones.
            web_content.body += reviewer.chrome_html()
    else:
        ctx_name = type(context).__name__
        if ctx_name == "ReviewerBottomBar":
            if config.get("styleReviewer", True):
                web_content.head += _theme_shell(theme_vars)
                web_content.head += _add_classes("awd-reviewer-bar")
                web_content.head += _css("reviewer", "backdrop.css")
            return
        is_bar = isinstance(context, TOOLBAR_CONTEXTS) or ctx_name in (
            "DeckBrowserBottomBar",
            "OverviewBottomBar",
        )
        if is_bar and config.get("styleToolbar", True):
            web_content.head += _theme_shell(theme_vars)
            web_content.head += _add_classes("awd-toolbar")
            web_content.head += _css("dashboard", "toolbar.css")


def on_state_change(new_state: str, old_state: str) -> None:
    # Screens that draw their own chrome hide Anki's bars; the rest get
    # them back.
    dashboard.apply_bar_visibility(new_state)


def on_answer(*args) -> None:
    stats.invalidate_cache()


def on_theme_change() -> None:
    stats.invalidate_cache()
    qt_theme.apply_app_palette()
    try:
        # Fade the open pages into the new palette rather than re-rendering
        # them, which would cut hard and drop the scroll position.
        qt_theme.animate_theme_change()
        mw.toolbar.draw()
    except Exception:
        pass


def on_profile_open() -> None:
    stats.invalidate_cache()
    qt_theme.apply_app_palette()


def setup_menu() -> None:
    from aqt.qt import QAction

    from .core.translations import tr
    from .ui.settings import AwdSettingsDialog

    action = QAction(tr("awd_settings"), mw)
    action.triggered.connect(lambda _: AwdSettingsDialog(mw).exec())
    mw.form.menuTools.addAction(action)



def install_bar_guards() -> None:
    dashboard.install_bar_guards()


gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
gui_hooks.webview_did_receive_js_message.append(bridge.handle_message)
gui_hooks.card_will_show.append(card_skin.on_card_will_show)
gui_hooks.state_shortcuts_will_change.append(card_skin.on_state_shortcuts)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.state_did_change.append(on_state_change)
gui_hooks.theme_did_change.append(on_theme_change)
gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.main_window_did_init.append(setup_menu)
gui_hooks.main_window_did_init.append(install_bar_guards)
