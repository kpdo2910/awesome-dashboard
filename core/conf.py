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
