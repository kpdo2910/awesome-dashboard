"""Universal card skin for the review screen (per-deck opt-in).

Decks with the skin on get their cards re-dressed at display time via
card_will_show. The question side is only wrapped in the styled shell, so no
answer can leak; the answer side is rebuilt from the note's fields.

Field roles come from field names (Vietnamese/English/Japanese). Cloze notes
get the shell only.
"""

import html as html_mod
import os
import re
import unicodedata

from aqt import mw

from ..core import conf
from ..core.translations import tr

# Role detection order matters: first match wins (e.g. Basic's "Front" must
# hit "word" before anything else).
ROLE_PATTERNS = [
    ("word", ("expression", "word", "kanji", "vocab", "front", "tu vung",
              "target", "question")),
    ("reading", ("reading", "kana", "furigana", "cach doc", "yomi",
                 "hiragana", "pinyin", "romaji")),
    ("meaning", ("meaning", "nghia", "definition", "translation", "back",
                 "viet", "english", "answer", "mean")),
    ("example", ("example", "sentence", "vi du", "vd", "usage", "context",
                 "cau")),
    ("notes", ("note", "bonus", "ghi chu", "memo", "mnemonic", "am han",
               "hint", "extra", "comment", "other")),
    ("image", ("image", "picture", "hinh", "anh", "img", "photo")),
    ("audio", ("audio", "sound", "phat am", "pronunciation")),
    ("tag", ("loai tu", "part of speech", "word type", "pos", "type",
             "loai")),
]

SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")
IMG_RE = re.compile(r"<img[^>]+src=[\"']?([^\"'>]+)[\"']?[^>]*>", re.I)
TAG_STRIP_RE = re.compile(r"<[^>]+>")
BR_SPLIT_RE = re.compile(r"<br\s*/?>|\n", re.I)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # NFD strips combining marks, but "đ" is its own letter with no canonical
    # decomposition — without this, a field named "Cách đọc" normalises to
    # "cach đoc" and never matches the "cach doc" pattern.
    return text.replace("đ", "d")


def _role_for(field_name: str):
    name = _norm(field_name)
    for role, keys in ROLE_PATTERNS:
        for key in keys:
            if key in name:
                return role
    return None


# --- per-deck enablement -----------------------------------------------------

def _deck_chain_ids(did: int):
    """The deck and its ancestors (nearest first), resolved by name."""
    ids = []
    try:
        name = mw.col.decks.name(did)
        parts = name.split("::")
        for i in range(len(parts), 0, -1):
            candidate = mw.col.decks.id_for_name("::".join(parts[:i]))
            if candidate:
                ids.append(int(candidate))
    except Exception:
        ids = [int(did)]
    return ids or [int(did)]


def skin_enabled_for_deck(did: int) -> bool:
    mapping = conf.get().get("cardSkinDecks") or {}
    if not isinstance(mapping, dict) or not mapping:
        return False
    for deck_id in _deck_chain_ids(did):
        value = mapping.get(str(deck_id))
        if value is not None:
            return bool(value)
    return False


def toggle_deck(did: int) -> bool:
    config = conf.get()
    mapping = dict(config.get("cardSkinDecks") or {})
    new_value = not skin_enabled_for_deck(did)
    mapping[str(did)] = new_value
    config["cardSkinDecks"] = mapping
    conf.save(config)
    return new_value


def _card_deck_id(card) -> int:
    try:
        return int(card.current_deck_id())
    except Exception:
        return int(getattr(card, "odid", 0) or card.did)


# --- content helpers -----------------------------------------------------------

def _clean(value: str, keep_html: bool = False) -> str:
    """Strip sound tags and images; optionally strip all other HTML too."""
    value = SOUND_RE.sub("", value or "")
    value = IMG_RE.sub("", value)
    if not keep_html:
        value = TAG_STRIP_RE.sub(" ", value)
        value = html_mod.unescape(value)
    return value.strip("  \r\n\t-–")


def _collect(note):
    """Bucket note fields into design roles."""
    buckets = {}
    sounds = []
    images = []
    for name, value in note.items():
        if not (value or "").strip():
            continue
        sounds.extend(SOUND_RE.findall(value))
        images.extend(match for match in IMG_RE.findall(value))
        role = _role_for(name)
        if role in (None, "notes"):
            buckets.setdefault("notes", []).append(_clean(value, keep_html=True))
        elif role in ("image", "audio"):
            continue  # media already captured above
        else:
            buckets.setdefault(role, []).append(_clean(value, keep_html=(role in ("meaning", "example"))))
    return buckets, sounds, images


def _progress(card):
    """(done_today, total_today) for the card's deck subtree."""
    try:
        remaining = sum(mw.col.sched.counts(card))
    except Exception:
        try:
            remaining = sum(mw.col.sched.counts())
        except Exception:
            return None
    try:
        did = _card_deck_id(card)
        deck_ids = mw.col.decks.deck_and_child_ids(did)
        ids_csv = ",".join(str(int(i)) for i in deck_ids)
        start_ms = (mw.col.sched.day_cutoff - 86400) * 1000
        done = mw.col.db.scalar(
            "SELECT count() FROM revlog r JOIN cards c ON r.cid = c.id"
            f" WHERE r.id > ? AND r.type IN (0,1,2,3) AND c.did IN ({ids_csv})",
            start_ms,
        ) or 0
    except Exception:
        done = 0
    total = done + max(0, remaining)
    return (done, total) if total > 0 else None


def _progress_html(card) -> str:
    stats = _progress(card)
    if not stats:
        return ""
    done, total = stats
    percent = min(100, round(done * 100 / total))
    return (
        f'<div class="awd-skin-progress" data-count="{done}/{total}">'
        f'<i style="width:{percent}%"></i></div>'
    )


def _audio_button(sounds) -> str:
    if not sounds:
        return ""
    name = html_mod.escape(sounds[0], quote=True)
    return (
        f'<button class="awd-skin-audio" onclick="pycmd(\'awd:playfile:{name}\')"'
        ' title="&#9654;">'
        '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
        '<path d="M8 5.5v13l11-6.5z"/></svg></button>'
    )


def _fold(summary: str, body_html: str, accent: bool = False) -> str:
    cls = "awd-skin-fold accent" if accent else "awd-skin-fold"
    return (
        f'<details class="{cls}"><summary>{summary}</summary>'
        f'<div class="awd-skin-fold-body">{body_html}</div></details>'
    )


def _meanings_html(meanings) -> str:
    items = []
    for chunk in meanings:
        items.extend(p.strip() for p in BR_SPLIT_RE.split(chunk) if p.strip())
    if not items:
        return ""
    if len(items) == 1:
        return f'<div class="awd-skin-meaning single">{items[0]}</div>'
    lis = "".join(f"<li>{item}</li>" for item in items)
    return f'<ol class="awd-skin-meaning">{lis}</ol>'


def play_file(filename: str) -> None:
    """Bridge target for the skin's audio button."""
    try:
        from aqt.sound import av_player

        path = os.path.join(mw.col.media.dir(), filename)
        if os.path.exists(path):
            av_player.play_file(path)
    except Exception as e:
        print(f"[Awesome Dashboard] play_file failed: {e}")


def install_space_toggle() -> None:
    """Space (and Enter) on a skinned answer flips the card back and forth
    instead of rating it; rating stays on the 1-4 keys and the buttons."""
    from aqt.reviewer import Reviewer

    if getattr(Reviewer, "_awd_space_wrapped", False):
        return
    original = Reviewer.onEnterKey

    def wrapped(self):
        try:
            if (
                self.state == "answer"
                and self.card is not None
                and skin_enabled_for_deck(_card_deck_id(self.card))
            ):
                self.web.eval("if (window.AwdSkin) AwdSkin.toggleFlip();")
                return
        except Exception:
            pass
        original(self)

    Reviewer.onEnterKey = wrapped
    Reviewer._awd_space_wrapped = True


# --- arrow-key rating with fly-away animation ---------------------------------

ARROW_MAP = (
    ("Left", "left", 1),    # Again
    ("Up", "up", 2),        # Hard
    ("Down", "down", 3),    # Good
    ("Right", "right", 4),  # Easy
)


def _arrow_answer(direction: str, ease: int) -> None:
    reviewer = mw.reviewer
    if reviewer is None or reviewer.state != "answer" or reviewer.card is None:
        return
    try:
        if not skin_enabled_for_deck(_card_deck_id(reviewer.card)):
            return
    except Exception:
        return
    reviewer.web.eval(
        f"if (window.AwdSkin) AwdSkin.flyAnswer('{direction}', {ease});"
    )


def on_state_shortcuts(state: str, shortcuts: list) -> None:
    """Arrow keys rate the current (skinned) card; the JS side plays the
    fly-away animation and then sends the ease."""
    if state != "review":
        return
    for key, direction, ease in ARROW_MAP:
        shortcuts.append(
            (key, lambda d=direction, e=ease: _arrow_answer(d, e))
        )


# --- hook ------------------------------------------------------------------------

# The rendered question is cached so the answer side can embed it as the
# front face of the horizontal flip scene (click / Space toggles the two).
_question_cache = {"cid": None, "html": ""}


def _keys_hint() -> str:
    return (
        '<div class="awd-skin-keys">'
        f'<span class="k-again">← {tr("rate_again")}</span>'
        f'<span class="k-hard">↑ {tr("rate_hard")}</span>'
        f'<span class="k-good">↓ {tr("rate_good")}</span>'
        f'<span class="k-easy">→ {tr("rate_easy")}</span>'
        "</div>"
    )


def _flip_scene(progress: str, front_html: str, answer_card_html: str) -> str:
    return f"""{progress}<div class="awd-skin">
  <div class="awd-flip-scene" onclick="AwdSkin.click(event)">
    <div class="awd-flip-inner" id="awd-flip">
      <div class="awd-flip-face front">
        <div class="awd-skin-card question">{front_html}</div>
      </div>
      <div class="awd-flip-face back">{answer_card_html}</div>
    </div>
  </div>
  {_keys_hint()}
</div>"""


def _answer_page(progress: str, card, answer_card_html: str) -> str:
    """Wrap an answer card in the flip scene when the question is cached."""
    if _question_cache.get("cid") == card.id and _question_cache.get("html"):
        return _flip_scene(progress, _question_cache["html"], answer_card_html)
    return (
        f'{progress}<div class="awd-skin">'
        f'<div class="awd-flip-scene">{answer_card_html}</div>{_keys_hint()}</div>'
    )


def on_card_will_show(text: str, card, kind: str) -> str:
    if kind not in ("reviewQuestion", "reviewAnswer"):
        return text
    try:
        if not skin_enabled_for_deck(_card_deck_id(card)):
            return text
    except Exception:
        return text

    try:
        progress = _progress_html(card)
        if kind == "reviewQuestion":
            _question_cache["cid"] = card.id
            _question_cache["html"] = text
            return (
                f'{progress}<div class="awd-skin">'
                '<div class="awd-skin-card question" onclick="AwdSkin.reveal(event)">'
                f"{text}</div></div>"
            )

        note = card.note()
        notetype = note.note_type() if hasattr(note, "note_type") else note.model()
        if notetype.get("type") == 1:  # cloze: keep rendered content
            return _answer_page(
                progress, card, f'<div class="awd-skin-card answer">{text}</div>'
            )

        buckets, sounds, images = _collect(note)
        word = (buckets.get("word") or [""])[0]
        if not word:
            return _answer_page(
                progress, card, f'<div class="awd-skin-card answer">{text}</div>'
            )

        reading = (buckets.get("reading") or [""])[0]
        tag_text = (buckets.get("tag") or [""])[0]

        top_left = (
            f'<span class="awd-skin-chip">{html_mod.escape(tag_text)}</span>'
            if tag_text else "<span></span>"
        )
        stats = _progress(card)
        counter = (
            f'<span class="awd-skin-count">{stats[0]}/{stats[1]}</span>'
            if stats else ""
        )

        reading_html = (
            f'<div class="awd-skin-reading">{html_mod.escape(reading)}</div>'
            if reading else ""
        )
        word_html = (
            '<div class="awd-skin-wordrow">'
            f'<span class="awd-skin-word">{html_mod.escape(word)}</span>'
            f"{_audio_button(sounds)}</div>"
        )

        image_html = ""
        if images:
            src = html_mod.escape(images[0], quote=True)
            image_html = f'<div class="awd-skin-img"><img src="{src}"></div>'

        example_html = ""
        examples = [e for e in (buckets.get("example") or []) if e]
        if examples:
            example_html = _fold(
                tr("skin_example"),
                "".join(f"<p>{e}</p>" for e in examples),
                accent=True,
            )

        notes_html = ""
        notes = [n for n in (buckets.get("notes") or []) if n]
        if notes:
            notes_html = _fold(
                tr("skin_notes"),
                "".join(f"<p>{n}</p>" for n in notes),
            )

        answer_card = f"""<div class="awd-skin-card answer">
    <div class="awd-skin-top">{top_left}{counter}</div>
    <div class="awd-skin-center">{reading_html}{word_html}</div>
    <hr class="awd-skin-line">
    {_meanings_html(buckets.get("meaning") or [])}
    {image_html}
    {example_html}
    {notes_html}
  </div>"""
        return _answer_page(progress, card, answer_card)
    except Exception as e:
        print(f"[Awesome Dashboard] card skin failed: {e}")
        return text
