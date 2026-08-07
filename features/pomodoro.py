"""Pomodoro timer.

One QTimer on the main window drives the countdown, so it keeps running while
the user reviews or navigates. Views are passive: the timer pushes state into
whichever screen is showing. Finished sessions are counted per study day in the
collection config, so they survive restarts and sync.
"""

import json
from datetime import datetime

from aqt import mw
from aqt.qt import QApplication, QTimer

from ..core import conf
from ..core.translations import tr

SESSIONS_KEY = "awd_pomodoro_sessions"


class Pomodoro:
    def __init__(self):
        self.timer = QTimer(mw)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.phase = "idle"  # idle | focus | break
        self.paused = False
        self.remaining = 0
        self.total = 0

    # --- session bookkeeping -------------------------------------------------
    def _today_key(self) -> str:
        try:
            start = mw.col.sched.day_cutoff - 86400
            return datetime.fromtimestamp(start).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

    def sessions_today(self) -> int:
        try:
            data = mw.col.get_config(SESSIONS_KEY, None) or {}
        except Exception:
            data = {}
        if data.get("date") != self._today_key():
            return 0
        try:
            return int(data.get("count", 0))
        except (TypeError, ValueError):
            return 0

    def _add_session(self) -> None:
        try:
            count = self.sessions_today() + 1
            mw.col.set_config(SESSIONS_KEY, {"date": self._today_key(), "count": count})
        except Exception:
            pass

    # --- controls ------------------------------------------------------------
    def _minutes(self, key: str, fallback: int) -> int:
        try:
            return max(1, min(180, int(conf.get().get(key, fallback))))
        except (TypeError, ValueError):
            return fallback

    def start_focus(self) -> None:
        self.phase = "focus"
        self.paused = False
        self.total = self.remaining = self._minutes("pomodoroFocusMinutes", 25) * 60
        self.timer.start()
        self.push()

    def start_break(self) -> None:
        self.phase = "break"
        self.paused = False
        self.total = self.remaining = self._minutes("pomodoroBreakMinutes", 5) * 60
        self.timer.start()
        self.push()

    def toggle_pause(self) -> None:
        if self.phase == "idle":
            self.start_focus()
            return
        self.paused = not self.paused
        if self.paused:
            self.timer.stop()
        else:
            self.timer.start()
        self.push()

    def reset(self) -> None:
        self.timer.stop()
        self.phase = "idle"
        self.paused = False
        self.remaining = 0
        self.total = 0
        self.push()

    def skip(self) -> None:
        """Skip the rest of the current phase and move on."""
        if self.phase == "focus":
            self._finish_focus(skipped=True)
        elif self.phase == "break":
            self.reset()

    # --- engine ----------------------------------------------------------
    def _tick(self) -> None:
        if self.paused or self.phase == "idle":
            return
        self.remaining -= 1
        if self.remaining > 0:
            self.push()
            return
        if self.phase == "focus":
            self._finish_focus()
        else:
            self._notify(tr("break_done"))
            self.reset()

    def _finish_focus(self, skipped: bool = False) -> None:
        if not skipped:
            self._add_session()
            self._notify(tr("focus_done"))
        self.start_break()

    def _notify(self, message: str) -> None:
        try:
            QApplication.beep()
        except Exception:
            pass
        try:
            from aqt.utils import tooltip
            tooltip(message, period=4000)
        except Exception:
            pass

    # --- view sync ---------------------------------------------------------
    def state(self) -> dict:
        idle = self.phase == "idle"
        return {
            "phase": self.phase,
            "paused": self.paused,
            "remaining": max(0, self.remaining),
            "total": self.total,
            "sessions": self.sessions_today(),
            "focusMin": self._minutes("pomodoroFocusMinutes", 25),
            # Pre-translated: the reviewer chrome renders straight from this
            # payload and has no i18n table of its own like the dashboard does.
            "phaseLabel": (
                tr("pomodoro_idle") if idle
                else tr("focus") if self.phase == "focus"
                else tr("break_")
            ),
            "actionLabel": (
                tr("start") if idle else tr("resume") if self.paused else tr("pause")
            ),
            "skipLabel": tr("skip"),
        }

    def push(self) -> None:
        """Push state into whichever screen is showing — the dashboard card or the
        reviewer's pinned widget. Other screens have no view to update.
        """
        try:
            payload = json.dumps(self.state())
            if mw.state == "deckBrowser":
                web = getattr(mw.deckBrowser, "web", None)
                if web:
                    web.eval(f"if (window.Awd) Awd.pomRender({payload});")
            elif mw.state == "review":
                web = getattr(mw.reviewer, "web", None)
                if web:
                    web.eval(f"if (window.AwdRev) AwdRev.pomRender({payload});")
        except Exception:
            pass


_instance = None


def get() -> Pomodoro:
    global _instance
    if _instance is None:
        _instance = Pomodoro()
    return _instance
