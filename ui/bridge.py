"""Handles the dashboard's custom pycmd messages (namespace "awd:").

Standard deck commands are left to Anki's own DeckBrowser._linkHandler.
Collapse/expand is handled here instead: the native command re-renders the
whole page, while this toggles the DOM client-side and just persists the state.
"""

from aqt import mw

from ..core import conf
from ..features import pomodoro


def _set_collapsed(raw_did: str, collapsed: bool) -> None:
    """Persist a deck's collapsed state without re-rendering the page."""
    try:
        did = int(raw_did)
    except (TypeError, ValueError):
        return
    if not mw.col:
        return
    try:
        from anki.decks import DeckCollapseScope, DeckId

        mw.col.decks.set_collapsed(
            DeckId(did), collapsed, DeckCollapseScope.REVIEWER
        )
    except Exception:
        # Older Anki: legacy toggle (only flip when it differs from target).
        try:
            deck = mw.col.decks.get(did)
            if deck is not None and bool(deck.get("collapsed")) != collapsed:
                mw.col.decks.collapse(did)
        except Exception:
            pass


def _open_deck(raw_did: str) -> None:
    """Open a subdeck from the overview's subdeck list."""
    try:
        did = int(raw_did)
    except (TypeError, ValueError):
        return
    try:
        mw.col.decks.select(did)
        mw.onOverview()
    except Exception as e:
        print(f"[Awesome Dashboard] open deck failed: {e}")


def _deck_action(action: str) -> None:
    """Rename/export the current deck from the overview footer."""
    try:
        did = int(mw.col.decks.get_current_id())
    except Exception:
        return
    from .settings import _run_deck_action

    _run_deck_action(action, did)


def _open_settings() -> None:
    from .settings import AwdSettingsDialog

    AwdSettingsDialog(mw).exec()


def _restart_anki() -> None:
    """Close Anki gracefully (collection is saved) and launch a fresh instance.

    A detached helper waits for this process to exit, so the new instance never
    trips over the profile lock.
    """
    import os
    import subprocess
    import sys

    pid = os.getpid()
    spawned = False
    try:
        if sys.platform == "darwin":
            # .../Anki.app/Contents/MacOS/anki -> .../Anki.app
            bundle = os.path.normpath(
                os.path.join(os.path.dirname(sys.executable), "..", "..")
            )
            if bundle.endswith(".app"):
                relaunch = f'/usr/bin/open -n "{bundle}"'
            else:
                relaunch = f'"{sys.executable}"'
            subprocess.Popen(
                ["/bin/sh", "-c",
                 f"while /bin/kill -0 {pid} 2>/dev/null; do sleep 0.3; done; {relaunch}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            spawned = True
        elif sys.platform.startswith("win"):
            exe = sys.executable or os.path.abspath(sys.argv[0])
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command",
                 f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue;"
                 f" Start-Process '{exe}'"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            spawned = True
        else:
            exe = os.path.abspath(sys.argv[0])
            subprocess.Popen(
                ["/bin/sh", "-c",
                 f"while kill -0 {pid} 2>/dev/null; do sleep 0.3; done; \"{exe}\" &"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            spawned = True
    except Exception as e:
        print(f"[Awesome Dashboard] restart helper failed: {e}")

    if spawned:
        from aqt.qt import QTimer

        QTimer.singleShot(150, mw.close)


def _sync() -> None:
    handler = getattr(mw, "on_sync_button_clicked", None) or getattr(mw, "onSync", None)
    if handler:
        handler()


def handle_message(handled, message: str, context):
    if not isinstance(message, str) or not message.startswith("awd:"):
        return handled

    command = message[len("awd:"):]
    if command == "add":
        import aqt
        aqt.dialogs.open("AddCards", mw)
    elif command == "browse":
        import aqt
        aqt.dialogs.open("Browser", mw)
    elif command == "stats":
        mw.onStats()
    elif command == "sync":
        _sync()
    elif command == "home":
        # moveToState runs the reviewer's own cleanup on the way out.
        mw.moveToState("deckBrowser")
    elif command == "settings":
        _open_settings()
    elif command == "restart":
        _restart_anki()
    elif command == "welcome_done":
        conf.set_value("shownWelcome", True)
    elif command.startswith("collapse:"):
        parts = command.split(":")
        if len(parts) == 3:
            _set_collapsed(parts[1], parts[2] == "1")
    elif command.startswith("opendeck:"):
        _open_deck(command[len("opendeck:"):])
    elif command.startswith("deck:"):
        _deck_action(command[len("deck:"):])
    elif command.startswith("sidebar:"):
        mode = command.split(":", 1)[1]
        if mode in ("full", "compact", "hidden"):
            # The page already switched client-side; just persist the choice.
            conf.set_value("sidebarMode", mode)
    elif command == "pom:toggle":
        pomodoro.get().toggle_pause()
    elif command == "pom:reset":
        pomodoro.get().reset()
    elif command == "pom:skip":
        pomodoro.get().skip()
    elif command.startswith("playfile:"):
        from ..screens import card_skin

        card_skin.play_file(command[len("playfile:"):])
    elif command == "debug":
        _push_debug_state()
    elif command == "debugshot":
        _debug_screenshot_settings()
    return (True, None)


def _debug_screenshot_settings() -> None:
    """Dev helper: render the settings dialog (and its calendar) to PNGs."""
    try:
        from aqt.qt import QTimer

        from .settings import AwdSettingsDialog

        dialog = AwdSettingsDialog(mw)
        dialog.show()

        def snap():
            try:
                dialog.grab().save("/tmp/awd_settings_shot.png")
            except Exception as e:
                print(f"[Awesome Dashboard] debugshot save failed: {e}")
            finally:
                dialog.close()

        QTimer.singleShot(700, snap)
    except Exception as e:
        print(f"[Awesome Dashboard] debugshot failed: {e}")


def _push_debug_state() -> None:
    """Dump bar/guard state into the dashboard page (window.__awdDebug)."""
    import json

    try:
        info = {
            "state": mw.state,
            "bottomHidden": mw.bottomWeb.isHidden(),
            "bottomHeight": mw.bottomWeb.height(),
            "toolbarHidden": mw.toolbarWeb.isHidden(),
            "guards": len(getattr(mw, "_awd_bar_guards", [])),
            "hideBottomConf": conf.get().get("hideNativeBottomBar"),
            "hideToolbarConf": conf.get().get("hideNativeToolbar"),
            "guardStats": [
                getattr(g, "stats", None)
                for g in getattr(mw, "_awd_bar_guards", [])
            ],
        }
    except Exception as e:
        info = {"error": str(e)}
    try:
        mw.deckBrowser.web.eval(f"window.__awdDebug = {json.dumps(info)};")
    except Exception:
        pass
