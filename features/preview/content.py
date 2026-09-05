"""Turning a rendered card side into something a grid tile can show.

**No `aqt` in this module** — `tools/test_preview.py` loads it directly.

`TemplateRenderOutput.question_text` / `.answer_text` are not finished HTML.
The backend leaves placeholders behind for Anki's own front-end to fill in, and
a page that drops them straight into the DOM prints `[anki:play:q:0]` at the
reader — which looks like a rendering bug rather than a missing feature. The
four it leaves are handled here.
"""

import html
import re

# `[anki:play:{side}:{index}]`, index into the side's own av tag list.
PLAY = re.compile(r"\[anki:play:([qa]):(\d+)\]")

# `[[type:Front]]`, `[[type:nc:Front]]`, `[[type:cloze:Text]]`. There is no
# input box in a grid tile, so the whole placeholder goes.
TYPE_ANSWER = re.compile(r"\[\[type:[^\]]*\]\]")

# The backend normally lifts these into av tags, but an unrendered one would
# otherwise show its markers around the text it speaks.
TTS = re.compile(r"\[anki:tts[^\]]*\](.*?)\[/anki:tts\]", re.DOTALL)

# Templates write the answer separator both ways, and some add a slash.
ANSWER_RULE = re.compile(r"<hr\s+id=[\"']?answer[\"']?\s*/?>", re.IGNORECASE)

SCRIPT = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.DOTALL | re.IGNORECASE)
STYLE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.DOTALL | re.IGNORECASE)
# A canvas is painted by script, and the script is about to go. Image
# Occlusion renders one over its picture; left in, it covers the picture
# with a blank box, and removing it degrades the tile to the plain image.
CANVAS = re.compile(r"<canvas\b[^>]*>.*?</canvas\s*>", re.DOTALL | re.IGNORECASE)
HANDLER = re.compile(r"""\son[a-zA-Z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""")

# An absolute font size written into a field. Anki's own `.card` rule is
# 20px, so that is what one of these was sized against.
FONT_SIZE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)
CARD_FONT_PX = 20.0

TAG = re.compile(r"<[^>]+>")
# Anything that is worth a tile even with no text in it.
VISUAL = re.compile(r"<(img|svg|video|audio)\b", re.IGNORECASE)


def strip_scripts(text: str) -> str:
    """Remove template JS and CSS, and inline event handlers with them.

    A page of twenty-four tiles runs twenty-four copies of whatever the note
    type ships. `{{hint:}}`'s own script fights the grid for the click, a
    template `<style>` block is page-wide because nothing scopes it, and one
    broken template would take the whole screen down. Canvases go with the
    scripts that would have painted them.
    """
    text = SCRIPT.sub("", text)
    text = STYLE.sub("", text)
    text = CANVAS.sub("", text)
    return HANDLER.sub("", text)


def audio_button(filename: str) -> str:
    """A play button for one media file.

    Same class and same pycmd as the reviewer's — `screens/card_skin.py` builds
    the skin's own from a note's sound fields, this one from a placeholder in
    template HTML — so one stylesheet rule and one bridge handler serve both.
    """
    name = html.escape(filename, quote=True)
    return (
        f'<button class="awd-skin-audio" onclick="pycmd(\'awd:playfile:{name}\')"'
        ' title="&#9654;">'
        '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
        '<path d="M8 5.5v13l11-6.5z"/></svg></button>'
    )


def replace_play(text: str, filenames) -> str:
    """Swap `[anki:play:…]` for play buttons, dropping the ones with no file.

    A TTS tag has no filename to hand to the player, so its placeholder is
    simply removed rather than left as a button that cannot do anything.
    """

    def swap(match):
        try:
            name = filenames[int(match.group(2))]
        except (IndexError, TypeError, ValueError):
            return ""
        return audio_button(name) if name else ""

    return PLAY.sub(swap, text)


def back_only(question_text: str, answer_text: str) -> str:
    """The answer side with the repeated question taken off the front.

    Nearly every template opens with `{{FrontSide}}<hr id=answer>`, and a card
    that shows its own question again on the back wastes the half of the tile
    the answer needed. `<hr id=answer>` is the marker Anki itself splits on;
    templates that leave it out are caught by the prefix test instead.
    """
    parts = ANSWER_RULE.split(answer_text, 1)
    if len(parts) == 2:
        return parts[1]
    if question_text and answer_text.startswith(question_text):
        return answer_text[len(question_text):]
    return answer_text


def rescale_fonts(text: str) -> str:
    """Absolute inline font sizes made relative to the tile.

    The note type's stylesheet is left out on purpose, but an inline
    `style` is not — it is how most people actually style a field, and
    dropping it would flatten every card to one voice. The trouble is that
    those sizes were chosen for a full screen: a vocabulary deck writes
    `font-size: 100px` for the word, which in a 270px tile is one and a
    half characters.

    Converting to `em` against Anki's own 20px card default keeps the
    author's hierarchy — the word still dwarfs the example sentence — and
    lets the tile's own text-size control scale the whole thing.
    """

    def swap(match):
        size = float(match.group(1)) / CARD_FONT_PX
        return f"font-size:{size:.3f}".rstrip("0").rstrip(".") + "em"

    return FONT_SIZE.sub(swap, text)


def clean(text: str, filenames=None) -> str:
    """One card side, ready to be written into a tile."""
    text = strip_scripts(text)
    text = rescale_fonts(text)
    text = TTS.sub(r"\1", text)
    text = TYPE_ANSWER.sub("", text)
    text = replace_play(text, filenames or [])
    return text.strip()


def is_blank(text: str) -> bool:
    """True when a side would draw as an empty tile.

    An image-only or audio-only side is not blank; a side of nothing but
    markup and whitespace is, and the tile says so rather than looking broken.
    """
    if VISUAL.search(text):
        return False
    stripped = TAG.sub(" ", text)
    stripped = html.unescape(stripped).replace("\xa0", " ")
    return not stripped.strip()


# A tile is a few hundred pixels; nothing legible in one needs more markup than
# this. The cap exists for the pathological note — a base64 data URI, a pasted
# web page — whose one field would otherwise dominate a whole page's payload.
MAX_FACE = 6000


def cap(text: str) -> str:
    """Long markup reduced to its words, so one note cannot bloat a page.

    Truncating HTML is not an option: a cut through a tag leaves the rest of
    the grid inside whatever element was left open.
    """
    if len(text) <= MAX_FACE:
        return text
    words = html.escape(" ".join(TAG.sub(" ", text).split()))
    return words[:MAX_FACE] + "…"
