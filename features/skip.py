"""Skip the current card — set it aside for the rest of this review session.

The card is buried, which is the only "not now" the scheduler offers, and
every card skipped this way is un-buried the moment the review screen is
left, so a skip never costs a card until tomorrow the way a plain bury does.
Modelled on the Advanced Review Bottom Bar add-on's Skip (its default key is C
too), whose users asked for the same thing here.
"""

from aqt import mw

from ..core import conf

# Card ids buried by skip since the review screen was last left.
_skipped: set = set()


def key() -> str:
    """The shortcut as stored ("C", "Alt+C"); empty means no key."""
    return str(conf.get().get("skipKey") or "").strip()


def _reviewer():
    reviewer = getattr(mw, "reviewer", None)
    if reviewer is None or mw.state != "review" or reviewer.card is None:
        return None
    return reviewer


def skip_current() -> bool:
    reviewer = _reviewer()
    if reviewer is None:
        return False
    card_id = int(reviewer.card.id)
    try:
        # Stop the auto-grading clock first: left running, it could expire
        # and flip a card that is on its way out.
        from .autograde import controller as autograde

        autograde.session().reset()
    except Exception as e:
        print(f"[Awesome Dashboard] skip: could not stop the clock: {e}")

    from aqt.operations.scheduling import bury_cards
    from aqt.utils import tooltip

    from ..core.translations import tr

    def done(_changes) -> None:
        _skipped.add(card_id)
        tooltip(tr("skip_toast"))

    try:
        # The same operation as Anki's own `-` key, so the reviewer moves on
        # by itself (op_executed → nextCard) and the skip sits in the undo
        # stack like any other change.
        bury_cards(parent=mw, card_ids=[card_id]).success(done).run_in_background()
    except Exception as e:
        print(f"[Awesome Dashboard] skip failed: {e}")
        return False
    return True


def restore() -> None:
    """Un-bury everything skipped.

    Synchronous on purpose: `profile_will_close` runs with the collection
    about to go away, and a background op would not land in time. The other
    caller, `reviewer_will_end`, runs before the next screen gathers its
    counts, so the skipped cards are already due again when it draws.
    """
    if not _skipped:
        return
    ids = sorted(_skipped)
    _skipped.clear()
    if not mw.col:
        return
    try:
        mw.col.sched.unbury_cards(ids)
    except Exception as e:
        print(f"[Awesome Dashboard] restoring skipped cards failed: {e}")
        return
    try:
        mw.update_undo_actions()
    except Exception:
        pass


def on_state_shortcuts(state: str, shortcuts: list) -> None:
    if state != "review":
        return
    bound = key()
    if bound:
        shortcuts.append((bound, skip_current))


def install() -> None:
    from aqt import gui_hooks

    gui_hooks.state_shortcuts_will_change.append(on_state_shortcuts)
    gui_hooks.reviewer_will_end.append(restore)
    gui_hooks.profile_will_close.append(restore)
