"""Reviewer chrome — replaces Anki's top toolbar and answer bar during review.

The page keeps its own bars inside the reviewer webview: a header (back,
deck name, edit / more) and a footer (remaining counts, then either "Show
answer" or the four rating buttons). Everything routes through the reviewer's
native pycmd commands, and the rating buttons' intervals come from the
scheduler — never hardcoded, so they follow the user's deck settings and FSRS.
"""

import html
import json

from aqt import gui_hooks, mw

from ..core import conf
from ..core.translations import tr

ICONS = {
    "back": '<path d="M15 5.5 8.5 12l6.5 6.5"/>',
    "edit": '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"/><path d="M13.5 6.5l4 4"/>',
    "more": '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/>'
            '<circle cx="19" cy="12" r="1.6"/>',
}


def enabled() -> bool:
    return bool(conf.get().get("styleReviewer", True))


def _icon(name: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
        f' aria-hidden="true">{ICONS[name]}</svg>'
    )


def chrome_html() -> str:
    """Static shell appended to the reviewer page; JS fills in the state."""
    return f"""
<div class="awd-rev-top" id="awd-rev-top">
  <button class="awd-rev-btn awd-rev-back" onclick="pycmd('awd:home')"
          title="{html.escape(tr("home"))}">
    {_icon("back")}<span>{html.escape(tr("home"))}</span>
  </button>
  <div class="awd-rev-title" id="awd-rev-title"></div>
  <div class="awd-rev-tools">
    <button class="awd-rev-btn icon" onclick="pycmd('edit')"
            title="{html.escape(tr("edit_note"))}">{_icon("edit")}</button>
    <button class="awd-rev-btn icon" onclick="pycmd('more')"
            title="{html.escape(tr("more_actions"))}">{_icon("more")}</button>
  </div>
</div>
<div class="awd-rev-bottom" id="awd-rev-bottom">
  <div class="awd-rev-counts" id="awd-rev-counts"></div>
  <div class="awd-rev-actions" id="awd-rev-actions"></div>
</div>
"""


def _counts():
    """(new, learn, review, index-of-current) for the remaining queue."""
    reviewer = mw.reviewer
    try:
        v3 = getattr(reviewer, "_v3", None)
        if v3 is not None:
            index, counts = v3.counts()
            return list(counts), int(index)
    except Exception:
        pass
    try:
        return list(mw.col.sched.counts()), -1
    except Exception:
        return [0, 0, 0], -1


def _state_payload() -> dict:
    counts, index = _counts()
    show_counts = True
    try:
        show_counts = bool(mw.col.conf.get("dueCounts", True))
    except Exception:
        pass
    deck_name = ""
    try:
        deck_name = str(mw.col.decks.current()["name"]).replace("::", " › ")
    except Exception:
        pass
    return {
        "deck": deck_name,
        "counts": counts,
        "current": index,
        "showCounts": show_counts,
        "showAnswer": tr("show_answer"),
    }


def _answer_buttons() -> list:
    """Rating buttons with the scheduler's own interval strings."""
    reviewer = mw.reviewer
    labels = []
    try:
        v3 = getattr(reviewer, "_v3", None)
        if v3 is not None:
            labels = list(mw.col.sched.describe_next_states(v3.states))
    except Exception as e:
        print(f"[Awesome Dashboard] next-state labels unavailable: {e}")
    show_times = True
    try:
        show_times = bool(mw.col.conf.get("estTimes", True))
    except Exception:
        pass

    buttons = []
    try:
        pairs = reviewer._answerButtonList()
    except Exception as e:
        print(f"[Awesome Dashboard] answer button list failed: {e}")
        return []
    for ease, label in pairs:
        interval = ""
        if show_times and len(labels) >= ease:
            interval = labels[ease - 1]
        buttons.append(
            {"ease": int(ease), "label": str(label), "interval": str(interval)}
        )
    return buttons


def _eval(script: str) -> None:
    try:
        mw.reviewer.web.eval(script)
    except Exception:
        pass


def on_show_question(card) -> None:
    if not enabled():
        return
    _eval(
        "typeof AwdRev !== 'undefined' && AwdRev.question("
        f"{json.dumps(_state_payload())});"
    )


def on_show_answer(card) -> None:
    if not enabled():
        return
    payload = _state_payload()
    payload["buttons"] = _answer_buttons()
    _eval(
        "typeof AwdRev !== 'undefined' && AwdRev.answer("
        f"{json.dumps(payload)});"
    )


def install() -> None:
    gui_hooks.reviewer_did_show_question.append(on_show_question)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)
