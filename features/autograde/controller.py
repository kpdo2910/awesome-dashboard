"""Time-based review — the Anki-facing half. `rules.py` holds the thresholds.

    question   Show answer, over a draining bar; the bar running out shows it
    answer     the clock's grade, tentative until → (take it) or ← (Again)
"""

import functools
import time

from aqt import mw
from aqt.qt import QApplication, QTimer

from ...core import conf, decks
from . import rules

TICK_MS = 250


def settings_for_card(card):
    """Effective settings if auto-grading applies to this card, else None.

    Gated on `styleReviewer`: without the add-on's answer bar there is nowhere
    to show the grade and no way to hide Anki's buttons.
    """
    if card is None:
        return None
    config = conf.get()
    if not config.get("styleReviewer", True):
        return None
    try:
        chain = decks.chain_ids(decks.deck_id_for_card(card))
    except Exception:
        return None
    settings = rules.resolve(config, chain)
    return settings if settings["enabled"] else None


def _reviewer():
    reviewer = getattr(mw, "reviewer", None)
    if reviewer is None or mw.state != "review" or reviewer.card is None:
        return None
    return reviewer


def _eases(reviewer) -> list:
    """Which ratings this card actually offers."""
    try:
        return [int(ease) for ease, _label in reviewer._answerButtonList()]
    except Exception as e:
        print(f"[Awesome Dashboard] answer button list failed: {e}")
        return [1, 2, 3, 4]


def _foreground() -> bool:
    """A card left on screen while the user is elsewhere must not time out
    into Again, so anything modal or unfocused stops the clock."""
    try:
        if QApplication.activeModalWidget() is not None:
            return False
        return bool(mw.isActiveWindow())
    except Exception:
        return True


class _Session:
    """The one card currently being timed."""

    def __init__(self):
        self.timer = QTimer(mw)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._tick)
        self.reset()

    def reset(self) -> None:
        self.timer.stop()
        self.card_id = None
        self.settings = None
        self.elapsed = 0.0
        self._last = 0.0
        self._paused = False
        # {"ease": int, "zone": str, "elapsed": ms} once a side has been picked.
        self.pending = None

    # --- question side ---------------------------------------------------

    def arm(self, card, settings: dict) -> None:
        self.reset()
        self.card_id = int(card.id)
        self.settings = settings
        self._last = time.monotonic()
        self.timer.start()

    def stop_clock(self) -> None:
        """Stop, taking the last partial tick with it: a discarded quarter
        second is enough to fall on the wrong side of a threshold."""
        if self.timer.isActive():
            self.timer.stop()
            if _foreground():
                self.elapsed += max(0.0, time.monotonic() - self._last)

    def _tick(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        self._last = now
        if self.settings is None:
            self.timer.stop()
            return
        if not _foreground():
            self._set_paused(True)
            return
        self._set_paused(False)
        self.elapsed += delta
        if self.elapsed >= self.settings["hardMax"]:
            self.timer.stop()
            self._expired()

    def _set_paused(self, paused: bool) -> None:

        if paused == self._paused:
            return
        self._paused = paused
        _eval(f"typeof AwdRev !== 'undefined' && AwdRev.gradePause({str(paused).lower()});")

    def _expired(self) -> None:
        """Out of time. `elapsed` is now past `hardMax`, which is the Again
        band by definition, so the grade needs no special case."""
        reviewer = self._live_reviewer("question")
        if reviewer is not None:
            self.flip(reviewer)

    def _live_reviewer(self, state: str):

        reviewer = _reviewer()
        if reviewer is None or reviewer.state != state:
            return None
        if self.card_id is None or int(reviewer.card.id) != self.card_id:
            return None
        return reviewer

    def elapsed_ms(self) -> int:
        return int(self.elapsed * 1000)

    def flip(self, reviewer) -> None:
        """Through `_getTypedAnswer`, not `_showAnswer`: it reads the
        `{{type:...}}` box out of the page first. `_showAnswer` alone leaves
        `typedAnswer` empty and every typed card comes back marked wrong.
        """
        self.stop_clock()
        try:
            collect = getattr(reviewer, "_getTypedAnswer", None)
            if collect is not None:
                collect()
            else:
                reviewer._showAnswer()
        except Exception as e:
            print(f"[Awesome Dashboard] could not show answer: {e}")


_session = None


def session() -> _Session:
    global _session
    if _session is None:
        _session = _Session()
    return _session


def _eval(script: str) -> None:
    try:
        web = getattr(mw.reviewer, "web", None)
        if web:
            web.eval(script)
    except Exception:
        pass


# --- the two keys ---------------------------------------------------------


def knew_it() -> bool:
    """→ : write the grade the clock picked. Answer side only."""
    state = session()
    reviewer = state._live_reviewer("answer")
    if reviewer is None or not state.pending:
        return False
    return answer(int(state.pending["ease"]))


def did_not_know() -> bool:
    """← : write Again instead."""
    state = session()
    reviewer = state._live_reviewer("answer")
    if reviewer is None:
        return False
    return answer(rules.failed(_eases(reviewer)))


def answer(ease: int) -> bool:
    reviewer = _reviewer()
    if reviewer is None or reviewer.state != "answer":
        return False
    session().pending = None
    try:
        reviewer._answerCard(ease)
    except Exception as e:
        print(f"[Awesome Dashboard] answering failed: {e}")
        return False
    return True


def undo() -> None:
    """The header's ↶."""
    try:
        session().reset()
        mw.undo()
    except Exception as e:
        print(f"[Awesome Dashboard] undo failed: {e}")


# --- hooks ----------------------------------------------------------------


def on_show_question(card) -> None:
    settings = settings_for_card(card)
    if settings is None:
        session().reset()
        return
    session().arm(card, settings)


def on_show_answer(card) -> None:
    """Here rather than in the key handlers: the answer can arrive by a key, a
    click, the bar running out or Anki's own auto-advance, and all four have to
    produce the same number."""
    state = session()
    state.stop_clock()
    state.pending = None
    if state.settings is None or state.card_id is None:
        return
    reviewer = _reviewer()
    if reviewer is None or int(reviewer.card.id) != state.card_id:
        return
    ease, zone = rules.grade(state.elapsed_ms(), state.settings, _eases(reviewer))
    state.pending = {"ease": ease, "zone": zone, "elapsed": state.elapsed_ms()}


def on_state_change(new_state: str, old_state: str) -> None:
    if new_state != "review":
        session().reset()


def guard_rating_shortcuts(state: str, shortcuts: list) -> None:
    """Neuter 1-4 while auto-grading is on.

    Anki builds this list once when the reviewer opens, but the feature is
    per-deck, so wrapping the callbacks decides per card where deleting the
    entries could not. Matched on what they call, not on the key, so a remap in
    Preferences is covered too.
    """
    if state != "review":
        return
    for index, entry in enumerate(shortcuts):
        try:
            key, handler = entry
        except (TypeError, ValueError):
            continue
        if not isinstance(handler, functools.partial):
            continue
        if getattr(handler.func, "__name__", "") != "_answerCard":
            continue
        shortcuts[index] = (key, _guarded(handler))


def _guarded(handler):
    def run():
        reviewer = _reviewer()
        if reviewer is not None and settings_for_card(reviewer.card) is not None:
            return
        handler()

    return run


def active_now() -> bool:

    reviewer = _reviewer()
    return reviewer is not None and settings_for_card(reviewer.card) is not None
