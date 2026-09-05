"""Item order, Learn mastery levels and Test question generation.

**No `aqt` in this module** — `tools/test_quizlet.py` loads it directly.

A session is a plain dict of JSON values so it can go straight into collection
config and come back days later. It holds *card ids*, not pool positions: the
pool is rebuilt from the deck every time the screen opens, and a card that was
deleted, suspended or moved in the meantime has to be able to fall out without
taking the rest of the session with it.
"""

from . import grading

MODES = ("cards", "learn", "test", "match")

# Learn: a term climbs one level per correct answer and drops one per miss.
# Three levels, three activities, and the last one is recall rather than
# recognition — a term is not learned because it was picked out of four.
LEVELS = 3
ACTIVITIES = ("tf", "choice", "typed")
ROUND_SIZE = 7

# A missed term comes back once more in the same round; after that it waits for
# the next one. Without the cap a term nobody can remember never lets the round
# end, which reads as the screen being stuck.
RETRIES_PER_ROUND = 1

CHOICE_OPTIONS = 4

# Both directions of every mode. "mixed" decides per question.
DIRECTIONS = ("term", "definition", "mixed")

TEST_TYPES = ("tf", "choice", "typed")
DEFAULT_TEST_TYPES = ("choice", "typed")
DEFAULT_TEST_LENGTH = 20
DEFAULT_MATCH_PAIRS = 6
MAX_MATCH_PAIRS = 12

VERSION = 1


def pick(count: int, wanted: int, rng) -> list:
    """`wanted` positions out of `count`, shuffled.

    Shuffled *before* the cap, not after: taking the first N of a deck order
    means the same N terms every session, which is how a 1300-card deck ends up
    teaching 250 of them forever.
    """
    order = list(range(max(0, int(count))))
    rng.shuffle(order)
    if wanted and wanted > 0:
        return order[:int(wanted)]
    return order


def direction_for(direction: str, index: int, rng) -> str:
    if direction == "mixed":
        return "term" if rng.random() < 0.5 else "definition"
    return direction if direction in ("term", "definition") else "term"


# --- Learn -----------------------------------------------------------------


def start_learn(card_ids, seed: int, direction: str = "term") -> dict:
    return {
        "v": VERSION,
        "mode": "learn",
        "seed": int(seed),
        "dir": direction if direction in DIRECTIONS else "term",
        "items": [int(cid) for cid in card_ids],
        "levels": [0] * len(card_ids),
        "queue": [],
        "retried": [],
        "round": 0,
        "answered": 0,
        "correct": 0,
        "streak": 0,
        "best": 0,
    }


def mastered(session: dict) -> int:
    return sum(1 for level in session.get("levels", []) if level >= LEVELS)


def progress(session: dict) -> dict:
    levels = session.get("levels") or []
    total = len(levels)
    done = sum(1 for level in levels if level >= LEVELS)
    # Partial credit, so the bar moves on every correct answer rather than only
    # when a term is finished — three answers of silence is a bar that looks
    # broken.
    earned = sum(min(level, LEVELS) for level in levels)
    return {
        "mastered": done,
        "total": total,
        "percent": round(earned / (total * LEVELS) * 100) if total else 0,
        "answered": int(session.get("answered", 0)),
        "correct": int(session.get("correct", 0)),
        "streak": int(session.get("streak", 0)),
        "best": int(session.get("best", 0)),
        "round": int(session.get("round", 0)),
    }


def finished(session: dict) -> bool:
    levels = session.get("levels") or []
    return bool(levels) and all(level >= LEVELS for level in levels)


def start_round(session: dict) -> list:
    """Fill the queue with the next batch, lowest level first.

    Lowest first rather than in order: the terms that keep being missed are the
    ones worth seeing again soonest, and a round of seven that mixes a brand
    new term with one on its last level feels like progress in a way that a
    straight pass down the list does not.
    """
    levels = session.get("levels") or []
    pending = [i for i, level in enumerate(levels) if level < LEVELS]
    pending.sort(key=lambda i: (levels[i], i))
    session["queue"] = pending[:ROUND_SIZE]
    session["retried"] = []
    session["round"] = int(session.get("round", 0)) + 1
    return session["queue"]


def next_item(session: dict):
    """Position of the term to ask, or None when the session is done."""
    if finished(session):
        return None
    if not session.get("queue"):
        return None
    return session["queue"][0]


def round_done(session: dict) -> bool:
    return not session.get("queue") and not finished(session)


def activity_for(level: int) -> str:
    return ACTIVITIES[max(0, min(len(ACTIVITIES) - 1, int(level)))]


def apply_answer(session: dict, position: int, correct: bool) -> dict:
    """Record one answer and move the queue on. Returns the new progress."""
    levels = session["levels"]
    if not 0 <= position < len(levels):
        return progress(session)

    session["answered"] = int(session.get("answered", 0)) + 1
    queue = session.get("queue") or []
    if position in queue:
        queue.remove(position)

    if correct:
        levels[position] = min(LEVELS, levels[position] + 1)
        session["correct"] = int(session.get("correct", 0)) + 1
        session["streak"] = int(session.get("streak", 0)) + 1
        session["best"] = max(int(session.get("best", 0)), session["streak"])
    else:
        levels[position] = max(0, levels[position] - 1)
        session["streak"] = 0
        retried = session.setdefault("retried", [])
        if retried.count(position) < RETRIES_PER_ROUND:
            retried.append(position)
            queue.append(position)

    session["queue"] = queue
    return progress(session)


def prune(session: dict, live_ids) -> dict:
    """Drop items whose card is gone, keeping every other item's level.

    A session that outlived an edit must not be thrown away wholesale; losing
    six months of a deck because one card was deleted is the sort of thing that
    stops people trusting a resume prompt at all.
    """
    live = set(int(cid) for cid in live_ids)
    items, levels = session.get("items") or [], session.get("levels") or []
    keep = [i for i, cid in enumerate(items) if int(cid) in live]
    remap = {old: new for new, old in enumerate(keep)}
    session["items"] = [items[i] for i in keep]
    session["levels"] = [levels[i] if i < len(levels) else 0 for i in keep]
    session["queue"] = [remap[p] for p in (session.get("queue") or []) if p in remap]
    session["retried"] = [remap[p] for p in (session.get("retried") or []) if p in remap]
    return session


# --- Test ------------------------------------------------------------------


def build_test(pool, answers, wanted: int, types, direction: str, seed: int) -> list:
    """A whole test up front, so the score cannot depend on how it was taken.

    `pool` is the prompt side and `answers` the answer side, both as plain
    strings, so this stays index arithmetic and never sees any HTML.
    """
    rng = grading.new_rng(seed)
    kinds = [kind for kind in (types or ()) if kind in TEST_TYPES] \
        or list(DEFAULT_TEST_TYPES)
    positions = pick(len(pool), wanted, rng)

    questions = []
    for index, position in enumerate(positions):
        kind = kinds[index % len(kinds)]
        side = direction_for(direction, index, rng)
        keys = answers if side == "term" else pool
        question = {"pos": position, "type": kind, "dir": side}
        if kind == "choice":
            question["options"] = grading.options_for(
                keys, position, CHOICE_OPTIONS, rng
            )
        elif kind == "tf":
            # Alternate rather than coin-flip: a run of six true answers in a
            # random sequence teaches the pattern, not the terms.
            truth = index % 2 == 0
            shown = position
            if not truth:
                wrong = grading.distractors(keys, position, 1, rng)
                if wrong:
                    shown = wrong[0]
                else:
                    truth = True
            question["shown"] = shown
            question["truth"] = truth
        questions.append(question)
    return questions


def score(questions, given) -> dict:
    """(right, total, percent) for a finished test."""
    total = len(questions)
    right = sum(1 for index in range(total) if given.get(str(index), {}).get("correct"))
    return {
        "right": right,
        "total": total,
        "percent": round(right / total * 100) if total else 0,
    }


# --- Match -----------------------------------------------------------------


def match_pairs(count: int, wanted: int, seed: int) -> list:
    rng = grading.new_rng(seed)
    wanted = max(2, min(MAX_MATCH_PAIRS, int(wanted or DEFAULT_MATCH_PAIRS)))
    return pick(count, min(wanted, count), rng)
