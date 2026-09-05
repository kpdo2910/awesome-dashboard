"""Restyle Anki's toast notifications to the add-on's palette.

`aqt.utils.tooltip` builds a QLabel with a hardcoded yellow palette and leaves
it in `aqt.utils._tooltipLabel`, so wrapping the function is the only way to
reach it. The wrapper also has to replace the name in every module that did
`from aqt.utils import tooltip` — `aqt.operations.collection` among them, which
is what undo calls.
"""

import sys

from ..core import conf, themes
from . import qt_theme


def _enabled() -> bool:
    return bool(conf.get().get("styleSystemScreens", True))


def _night() -> bool:
    try:
        from aqt.theme import theme_manager

        return bool(theme_manager.night_mode)
    except Exception:
        return False


RADIUS = 10


def _restyle(label) -> None:
    if label is None:
        return
    pal = themes.palette(conf.get().get("theme", "glass"), _night())
    bg = pal["bg"]
    # Inverted rather than a surface colour: a toast painted in the page's own
    # surface is invisible against the page, and a theme's text colour is by
    # definition the one that contrasts with its background.
    fill = qt_theme.flatten(pal["text"], bg)
    label.setObjectName("awdToast")
    label.setFrameStyle(0)
    # Anki turns this on to paint its yellow palette; left on, that colour wins
    # over the stylesheet and the toast keeps Anki's look in dark mode.
    label.setAutoFillBackground(False)
    label.setStyleSheet(
        f"QLabel#awdToast {{ background: {fill}; color: {bg};"
        f" border: none; font-size: 12.5px; font-weight: 500; }}"
    )
    label.adjustSize()
    _round(label)


def _round(label) -> None:
    """Qt does not clip a top-level widget's background to a QSS border-radius,
    so the corners have to come off as a window mask instead."""
    from aqt.qt import QPainterPath, QRectF, QRegion

    try:
        path = QPainterPath()
        path.addRoundedRect(QRectF(label.rect()), RADIUS, RADIUS)
        label.setMask(QRegion(path.toFillPolygon().toPolygon()))
    except Exception as e:
        print(f"[Awesome Dashboard] toast mask failed: {e}")


def install() -> None:
    import aqt.utils

    original = getattr(aqt.utils, "tooltip", None)
    if original is None or getattr(original, "_awd_wrapped", False):
        return

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        if _enabled():
            try:
                _restyle(getattr(aqt.utils, "_tooltipLabel", None))
            except Exception as e:
                print(f"[Awesome Dashboard] toast restyle failed: {e}")
        return result

    wrapped._awd_wrapped = True
    aqt.utils.tooltip = wrapped
    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "tooltip", None) is original:
            module.tooltip = wrapped
