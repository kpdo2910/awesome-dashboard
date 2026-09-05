"""Marking typed answers, and picking the wrong options for a question.

**No `aqt` in this module** — `tools/test_quizlet.py` loads it directly.
"""

import random
import re

from .fields import normalise_key, plain_text

# Below this many characters an answer gets no spelling tolerance at all.
# Almost every one-edit neighbour of a short word is another real word — "cat"
# for "car", "sun" for "son" — so slack there marks wrong answers right, which
# is the one failure a study tool cannot afford.
NO_SLACK_BELOW = 5

# Above it, one edit per this many characters. "receive" gets one, a fifteen
# character phrase gets two.
CHARS_PER_EDIT = 9

# Two answers this alike are the same answer as far as a question is concerned,
# so one of them must not be offered as the wrong option next to the other.
DUPLICATE_RATIO = 0.9


def _distance(left: str, right: str) -> int:
    """Damerau–Levenshtein, restricted (optimal string alignment).

    Adjacent transpositions cost one edit rather than two. Plain Levenshtein
    charges "recieve" two against "receive" — the same as a word that shares no
    ending at all — and no single tolerance can then let the slip through
    without letting real mistakes through with it.
    """
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    width = len(right)
    two_back = None
    previous = list(range(width + 1))
    for i, a in enumerate(left, 1):
        current = [i] + [0] * width
        for j, b in enumerate(right, 1):
            cost = 0 if a == b else 1
            value = min(previous[j] + 1, current[j - 1] + 1,
                        previous[j - 1] + cost)
            if (two_back is not None and j > 1
                    and a == right[j - 2] and left[i - 2] == b):
                value = min(value, two_back[j - 2] + cost)
            current[j] = value
        two_back, previous = previous, current
    return previous[width]


def slack_for(length: int) -> int:
    """Edits allowed against an expected answer of this length."""
    if length < NO_SLACK_BELOW:
        return 0
    return max(1, length // CHARS_PER_EDIT)


def similarity(given: str, expected: str) -> float:
    """0..1, on the normalised forms. 1.0 is an exact match."""
    a, b = normalise_key(given), normalise_key(expected)
    if not a or not b:
        return 1.0 if a == b else 0.0
    if a == b:
        return 1.0
    return 1.0 - _distance(a, b) / max(len(a), len(b))


def _alternatives(expected: str) -> list:
    """The answers a single field can legitimately be read as.

    Note fields routinely hold several synonyms separated by a comma, a slash
    or a semicolon, and a learner who types one of them knows the card. The
    whole string counts too, for the field that is genuinely one phrase
    containing a comma.
    """
    text = plain_text(expected)
    parts = [part.strip() for part in re.split(r"[,;/、；，]", text)]
    parts = [part for part in parts if normalise_key(part)]
    if len(parts) > 1:
        return [text] + parts
    return [text]


def check_typed(given: str, expected: str) -> tuple:
    """(correct, exact) for a typed answer.

    `exact` separates "right" from "right apart from a typo", so the screen can
    say *almost* and show the spelling instead of silently accepting it — which
    is how a misspelling becomes permanent. Every alternative is checked for an
    exact match before any of them is checked for a near one, or typing one
    synonym exactly would be reported as a misspelling of another.
    """
    typed = normalise_key(given)
    if not typed:
        return False, False
    options = [normalise_key(option) for option in _alternatives(expected)]
    options = [option for option in options if option]
    if typed in options:
        return True, True
    for option in options:
        if _distance(typed, option) <= slack_for(len(option)):
            return True, False
    return False, False


def distractors(pool, answer_index: int, count: int, rng) -> list:
    """`count` indices into `pool` that are wrong answers to `answer_index`.

    Options too close to the right answer are dropped rather than shuffled in:
    a multiple choice with two acceptable answers teaches the wrong thing, and
    it is the same failure whether the duplicate came from two notes sharing a
    meaning or from one note existing twice in the deck.
    """
    answer = normalise_key(pool[answer_index])
    candidates = [
        index for index, value in enumerate(pool)
        if index != answer_index
        and normalise_key(value)
        and normalise_key(value) != answer
        and similarity(value, pool[answer_index]) < DUPLICATE_RATIO
    ]
    # Deduplicate the options against each other as well, so a deck with three
    # copies of "to go" never shows it twice in one question.
    seen = set()
    unique = []
    for index in candidates:
        key = normalise_key(pool[index])
        if key not in seen:
            seen.add(key)
            unique.append(index)
    rng.shuffle(unique)
    return unique[:count]


def options_for(pool, answer_index: int, wanted: int, rng) -> list:
    """Shuffled option indices including the answer, at most `wanted` long."""
    chosen = distractors(pool, answer_index, max(0, wanted - 1), rng)
    chosen.append(answer_index)
    rng.shuffle(chosen)
    return chosen


def new_rng(seed: int) -> random.Random:
    """A generator that replays: resuming a session must not reshuffle it."""
    return random.Random(int(seed))
