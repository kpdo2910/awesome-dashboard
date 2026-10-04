"""What the running Anki's webview can actually render.

`min_point_version` stays low so older Anki keeps working — the CSS degrades on
its own. This is for the settings dialog, so it can hide controls whose effect
that build could never show. A slider that visibly does nothing is worse than no
slider at all.
"""

# color-mix() shipped in Chromium 111. Everything the add-on gates on needs it;
# backdrop-filter has been available since Chromium 76 and is not worth testing.
COLOR_MIX_CHROMIUM = 111

# Qt WebEngine bundles a fixed Chromium, so the Qt version is a usable fallback
# on builds too old to expose the Chromium version directly. Qt 6.6 was the
# first with Chromium 112.
COLOR_MIX_QT = (6, 6)


def _chromium_major():
    """Major Chromium version of the bundled webview, or None if unknown."""
    try:
        from PyQt6.QtWebEngineCore import qWebEngineChromiumVersion
    except Exception:
        return None
    try:
        return int(str(qWebEngineChromiumVersion()).split(".")[0])
    except (ValueError, IndexError):
        return None


def _qt_version():
    try:
        from aqt.qt import qtmajor, qtminor

        return (int(qtmajor), int(qtminor))
    except Exception:
        return None


def supports_color_mix() -> bool:
    """Whether the webview can render `color-mix()`.

    Unknown counts as supported: the API used below only exists from Qt 6.5, so
    a failure to detect means either a very old build — where the CSS falls back
    to solid panels anyway — or an unusual one that is probably modern. Hiding a
    control that does work is the worse mistake of the two.
    """
    chromium = _chromium_major()
    if chromium is not None:
        return chromium >= COLOR_MIX_CHROMIUM
    qt = _qt_version()
    if qt is not None:
        return qt >= COLOR_MIX_QT
    return True


def describe() -> str:
    """Human-readable webview version, for the About page."""
    chromium = _chromium_major()
    if chromium is not None:
        return f"Chromium {chromium}"
    qt = _qt_version()
    return f"Qt {qt[0]}.{qt[1]}" if qt else "—"


# Read once: Anki itself needs a restart for a different driver to take effect.
_driver = None


def _video_driver():
    """Anki's `VideoDriver`, or None where the API is missing."""
    global _driver
    if _driver is None:
        try:
            from aqt import mw

            read = getattr(mw.pm, "video_driver", None)
            _driver = read() if read else False
        except Exception:
            _driver = False
    return _driver or None


def software_renderer() -> bool:
    """Whether the webview runs with no GPU at all (`--disable-gpu`)."""
    driver = _video_driver()
    return bool(driver) and driver.value == "software"


def driver_label() -> str:
    """The driver's name as Anki's preferences spell it, for the About page."""
    driver = _video_driver()
    return driver.name if driver else "—"


def effects_reduced(config: dict) -> bool:
    """Whether the screens should drop blur and motion.

    Unset means automatic: on for the Software driver, where a blurred block
    was measured at over 100 ms a frame, off everywhere else. A stored bool is
    the user's own answer and wins either way.
    """
    value = config.get("reduceEffects")
    return value if isinstance(value, bool) else software_renderer()
