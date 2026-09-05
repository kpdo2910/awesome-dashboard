"""Which note field is the term, and which is the definition.

**No `aqt` in this module** — `tools/test_quizlet.py` loads it directly.

The study modes need the two sides of a card as separate strings: Match puts
them in different columns, Test uses one as the prompt and the other as the
answer key. Anki has no such concept, so it has to be derived.

Deriving it *by field position* is the obvious approach and it is wrong. The
add-on this feature was modelled on took `note.items()[0]` and `[1]`, which on
a note type whose first field is a row number gives a term of "1487" and a
definition of the word — the meaning never appears at all, and both cards of a
two-template note look identical because the card ordinal is never consulted.

So the pair comes from the card's own template: the fields `qfmt` renders are
candidates for the term, the fields `afmt` renders are candidates for the
definition, and the card ordinal picks which template. Two kinds of field are
skipped on the way: ones holding only media (an `audio` field is not a term)
and ones holding a row number, which are detected from the *data* rather than
from a list of names — `stt`, `STT`, `ID`, `#`, `序号` and every other spelling
look the same once you notice the values are all distinct integers.

The result is a default, not an answer. `awd_qz_fieldmap` overrides it per note
type, and the mode picker shows the current pair so a wrong guess is visible
before a session starts rather than halfway through it.
"""

import re
import unicodedata
from html.parser import HTMLParser

# {{...}} with no nested braces. A template that would defeat this would not
# render in Anki either.
_REPLACEMENT = re.compile(r"\{\{([^{}]*)\}\}")

# Names Anki resolves itself. None of them is a note field.
SPECIAL = frozenset({
    "FrontSide", "Tags", "Type", "Deck", "Subdeck", "Card", "CardFlag",
})

_SOUND = re.compile(r"\[sound:[^\]]*\]", re.I)
_ANKI_TTS = re.compile(r"\[anki:tts.*?\]", re.I | re.S)
_DROPPED = re.compile(r"(?is)<(script|style)\b.*?</\1>")
_MEDIA_TAG = re.compile(r"(?i)<(img|audio|video|source|object|embed)\b[^>]*>")
_TAG = re.compile(r"<[^>]*>")
_ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
_ENTITIES = {
    "nbsp": " ", "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
    "#39": "'", "hellip": "…", "mdash": "—", "ndash": "–",
}

# A row number is an integer, a decimal, or something like "12-3" / "No. 7".
_NUMERIC = re.compile(r"^[\s#.,\-/:_]*\d[\d\s#.,\-/:_]*$")

# How sure the sample has to be before a field is treated as a row number.
# Both tests matter: "1" repeated on every note is a level marker, not an
# index, and dropping it would cost a deck its only term field.
INDEX_NUMERIC_SHARE = 0.9
INDEX_DISTINCT_SHARE = 0.8
INDEX_MIN_SAMPLE = 8

# How many fields a side may hold. A question with three things in it is three
# questions, and a back long enough to scroll is a card, not an answer — the
# whole card is one button away under Details either way.
MAX_FRONT = 2
MAX_BACK = 3


def _unescape(text: str) -> str:
    def replace(match):
        name = match.group(1)
        if name.startswith("#x") or name.startswith("#X"):
            try:
                return chr(int(name[2:], 16))
            except ValueError:
                return match.group(0)
        if name.startswith("#"):
            try:
                return chr(int(name[1:]))
            except ValueError:
                return match.group(0)
        return _ENTITIES.get(name, match.group(0))

    return _ENTITY.sub(replace, text)


def plain_text(value: str) -> str:
    """Readable text of a field or a rendered side, with markup removed."""
    if not value:
        return ""
    text = _DROPPED.sub(" ", str(value))
    text = _SOUND.sub(" ", text)
    text = _ANKI_TTS.sub(" ", text)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6])>", " ", text)
    text = _TAG.sub(" ", text)
    text = _unescape(text)
    # NBSP survives \s in some Python builds' re; normalise it away by hand.
    return " ".join(text.replace(" ", " ").split())


def has_text(value: str) -> bool:
    return bool(plain_text(value))


def has_media(value: str) -> bool:
    if not value:
        return False
    return bool(_SOUND.search(value) or _ANKI_TTS.search(value)
                or _MEDIA_TAG.search(value))


def is_media_only(value: str) -> bool:
    """A field carrying a sound tag or an image and no words of its own."""
    return has_media(value) and not has_text(value)


def template_fields(fmt: str) -> list:
    """Note fields a template renders, in order of first appearance.

    Conditional sections contribute their *field* references but not the
    condition itself: `{{#Image}}{{Image}}{{/Image}}` yields `["Image"]`, so a
    section that happens to be empty on this note is filtered out later by the
    value check rather than here.
    """
    found = []
    for raw in _REPLACEMENT.findall(fmt or ""):
        name = raw.strip()
        if not name or name[0] in "#/^!":
            continue
        # Filters chain left to right: {{text:furigana:Reading}}. The field is
        # whatever survives the last colon.
        name = name.rsplit(":", 1)[-1].strip()
        if not name or name in SPECIAL or name in found:
            continue
        found.append(name)
    return found


def index_like_fields(samples: dict) -> set:
    """Fields whose sampled values look like row numbers.

    `samples` is {field name: [value, ...]} over notes of one note type. A
    field qualifies when almost every value is numeric *and* almost every value
    is different — an index counts up, a difficulty or level field repeats.
    """
    flagged = set()
    for name, values in samples.items():
        texts = [plain_text(value) for value in values]
        texts = [text for text in texts if text]
        if len(texts) < INDEX_MIN_SAMPLE:
            continue
        numeric = sum(1 for text in texts if _NUMERIC.match(text))
        if numeric / len(texts) < INDEX_NUMERIC_SHARE:
            continue
        if len(set(texts)) / len(texts) < INDEX_DISTINCT_SHARE:
            continue
        flagged.add(name)
    return flagged


def _usable(names, values: dict, index_fields, skip=()) -> list:
    """Candidates in template order: has words, is not media, is not an index."""
    return [
        name for name in names
        if name not in skip
        and has_text(values.get(name, ""))
        and not is_media_only(values.get(name, ""))
        and name not in index_fields
    ]


def _any_with_text(names, values: dict, skip=()) -> list:
    return [
        name for name in names
        if name not in skip and has_text(values.get(name, ""))
    ]


def choose(front_names, back_names, values: dict, index_fields=()) -> tuple:
    """(term field, definition field) for one card. Either may be None.

    Falls back to allowing an index field rather than returning nothing: a
    note type that is *only* numbers still deserves a usable pair, and the
    wrong-looking result is then visible on the mode picker.
    """
    index_fields = set(index_fields or ())

    terms = _usable(front_names, values, index_fields) \
        or _any_with_text(front_names, values)
    term = terms[0] if terms else None

    skip = (term,) if term else ()
    definitions = _usable(back_names, values, index_fields, skip) \
        or _any_with_text(back_names, values, skip)
    definition = definitions[0] if definitions else None

    return term, definition


def resolve(front_names, back_names, values: dict, index_fields=(),
            pinned=None) -> tuple:
    """(front fields, back fields) for one card, as two ordered lists.

    A side is a *set* of fields, not one: a Japanese card's back is a reading,
    a meaning and an example, and showing only the first of them makes the mode
    less useful than the card it came from. The **first** field of each side is
    the one being tested — it is what a typed answer is marked against, what a
    multiple choice offers and what a Match tile holds — and the rest is
    context shown alongside. Anything else needs a rule for how to compare a
    stack of fields to what someone typed, and there is no good one.

    `pinned` is `{"front": [...], "back": [...]}` from the collection; a side
    it does not name falls back to the guess. Each side is capped — see
    `MAX_FRONT` / `MAX_BACK` — here rather than only in the settings screen, so
    a pin written by an older build or edited by hand cannot put six fields on
    a question.
    """
    pinned = pinned or {}
    known = set(values)

    def pins(key):
        listed = pinned.get(key)
        if not isinstance(listed, list):
            return None
        kept = [name for name in listed if name in known]
        return kept or None

    front, back = pins("front"), pins("back")
    if front is None or back is None:
        auto_term, auto_definition = choose(
            front_names, back_names, values, index_fields
        )
        if front is None:
            front = [auto_term] if auto_term else []
        if back is None:
            back = [auto_definition] if auto_definition else []

    # Truncate the front first, then clear the overlap against what survived: a
    # field pushed off the front by the cap is free to be the answer.
    front = front[:MAX_FRONT]
    back = [name for name in back if name not in set(front)][:MAX_BACK]
    return front, back


# Formatting worth keeping in a study screen, plus the ruby tags a Japanese
# deck's readings live in. Everything else is unwrapped to its text.
KEEP_TAGS = frozenset({
    "b", "strong", "i", "em", "u", "s", "del", "sub", "sup", "small", "mark",
    "br", "hr", "span", "div", "p", "ul", "ol", "li", "code", "pre",
    "table", "thead", "tbody", "tr", "td", "th",
    "ruby", "rt", "rp", "rb", "img",
})
VOID_TAGS = frozenset({"br", "hr", "img"})
# `style`, `class` and `id` are dropped with everything else: a note template's
# own colours are chosen against a white card and are unreadable on a themed
# one, and an inline declaration outranks every rule the screen could write.
KEEP_ATTRS = {"img": ("src", "alt", "width", "height")}


class _Sanitiser(HTMLParser):
    """Rebuild a field's HTML from an allow-list.

    A regex pass over the markup is the usual shortcut and it is not safe
    enough here: this text is handed to the page inside a JSON payload, so a
    field containing a `<script>` — pasted in from a web page, which is how
    most note fields are made — would run in the study screen.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._suppress = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object", "embed"):
            self._suppress += 1
            return
        if self._suppress or tag not in KEEP_TAGS:
            return
        allowed = KEEP_ATTRS.get(tag, ())
        kept = "".join(
            f' {name}="{_attr_escape(value)}"'
            for name, value in attrs
            if name in allowed and value
        )
        self.out.append(f"<{tag}{kept}>" if tag not in VOID_TAGS
                        else f"<{tag}{kept}/>")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object", "embed"):
            self._suppress = max(0, self._suppress - 1)
            return
        if self._suppress or tag not in KEEP_TAGS or tag in VOID_TAGS:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._suppress:
            self.out.append(_text_escape(data))


def _attr_escape(value: str) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _text_escape(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def safe_html(value: str) -> str:
    """A field's markup with scripts, styling and stray attributes removed."""
    if not value:
        return ""
    text = _SOUND.sub("", str(value))
    text = _ANKI_TTS.sub("", text)
    parser = _Sanitiser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: cannot clean a field: {e}")
        return _text_escape(plain_text(value))
    return "".join(parser.out).strip()


def normalise_key(value: str) -> str:
    """Comparison form for "is this term already in the pool" checks.

    Accent-folded and punctuation-stripped so that two cards differing only by
    a trailing full stop are not offered as two different answers to the same
    question.
    """
    text = plain_text(value).casefold()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())
