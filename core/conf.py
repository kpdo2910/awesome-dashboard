"""Config helpers: read the add-on config merged over defaults."""

from aqt import mw

DEFAULTS = {
    "userName": "",
    "customGreeting": "",
    "theme": "glass",
    "customAccent": None,
    "language": "auto",
    "sidebarMode": "hidden",  # "full" | "compact" | "hidden"
    "showStats": True,
    "showHeatmap": True,
    "showPomodoro": True,
    # The habits themselves live in collection config, not here — this is only
    # whether the dashboard shows the block. See features/habits/store.py.
    "showHabits": True,
    "pomodoroFocusMinutes": 25,
    "pomodoroBreakMinutes": 5,
    "hideNativeBottomBar": True,
    "hideNativeToolbar": True,
    "styleOverview": True,
    "styleReviewer": True,
    "events": [],
    "cardSkinDecks": {},
    # The fallback for decks with no entry of their own, which is every deck
    # added after the add-on was installed.
    "cardSkinDefault": True,
    "styleToolbar": True,
    "styleSystemScreens": True,
    # Filename inside user_files/, not a path — see core/background.py.
    "backgroundImage": "",
    # How much of the theme background is laid over the image, as a percentage.
    # Light by default: the point of setting an image is to see it.
    "backgroundDim": 25,
    # How opaque the cards and sidebar are, as a percentage. Applies with or
    # without an image; 100 is the plain opaque look, so nothing changes until
    # the user asks for it.
    "cardOpacity": 100,
    # Blur applied to whatever shows through a translucent card, in pixels.
    # 0 leaves it sharp, which is the only way to actually read the image
    # through a card rather than see a smear of its colours.
    "cardBlur": 18,
    "shownWelcome": False,
    # Nav page the settings dialog reopens on. A page id, not an index, so
    # adding or reordering a nav entry cannot land the user somewhere else.
    "settingsPage": "general",
}

_ADDON = None


def _addon_package() -> str:
    global _ADDON
    if _ADDON is None:
        _ADDON = mw.addonManager.addonFromModule(__name__)
    return _ADDON


def get() -> dict:
    conf = dict(DEFAULTS)
    stored = mw.addonManager.getConfig(_addon_package()) or {}
    conf.update({k: v for k, v in stored.items() if v is not None})
    return conf


def save(conf: dict) -> None:
    mw.addonManager.writeConfig(_addon_package(), conf)


def set_value(key: str, value) -> None:
    conf = get()
    conf[key] = value
    save(conf)
