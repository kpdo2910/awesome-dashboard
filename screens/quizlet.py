"""Quizlet-style study modes, drawn into the deck overview's own webview.

**No second `AnkiWebView`.** A webview of our own would have to be parented to
something, and `AnkiWebView.__init__` appends itself to three `gui_hooks` that
only `cleanup()` removes — including one that fires after every collection
operation. The habit report was built that way once and froze the app. The
overview's webview already exists, Anki owns its lifetime, and it already
carries the theme variables, so a session renders into it and `Overview.
_renderPage` delegates here while one is open.

Python owns every rule and every number; `web/quizlet/quizlet.js` only draws
what it is handed — the same split as the habit report, and for the same
reason: a second implementation of "was that answer right" in JavaScript would
drift from the one that has tests.

The pool is built from the *card template*, not from field order — see
`features/quizlet/fields.py` for why that distinction is the whole feature.
"""

import copy
import html
import json
import random
import time

from aqt import mw

from ..core import conf
from ..core.translations import tr
from ..features.quizlet import fields, grading
from ..features.quizlet import session as qz
from ..features.quizlet.store import get_store

# Cards read into a session. Every mode draws from this pool, so it has to be
# big enough that Learn is not always the same fifty terms and small enough
# that opening the picker does not stall — a card costs one note fetch.
POOL_LIMIT = 400

# Notes sampled per note type when deciding which fields hold row numbers.
INDEX_SAMPLE = 200

MODES = ("cards", "learn", "test", "match")

# anki.consts.MODEL_CLOZE. Read as a literal rather than imported: it has never
# changed, and an import that moves would take the whole screen down with it.
CLOZE = 1

# The add-on config keys this screen reads, and their option names.
OPTION_KEYS = {
    "direction": "qzDirection",
    "testLength": "qzTestLength",
    "testTypes": "qzTestTypes",
    "matchPairs": "qzMatchPairs",
    "sessionSize": "qzSessionSize",
    "grade": "qzGrade",
}

_active = None
_index_cache = {}


# --- pool ------------------------------------------------------------------


def invalidate() -> None:
    """Forget the per-note-type index-field guesses.

    They are derived from note *content*, so importing a deck or editing a
    field can change the answer. Cheap to rebuild, so this is called on
    anything that could have.
    """
    _index_cache.clear()


def _index_fields(note_type) -> set:
    """Fields of this note type whose values look like row numbers."""
    ntid = int(note_type["id"])
    if ntid in _index_cache:
        return _index_cache[ntid]
    names = [field["name"] for field in note_type["flds"]]
    samples = {name: [] for name in names}
    try:
        rows = mw.col.db.list(
            "select flds from notes where mid = ? limit ?", ntid, INDEX_SAMPLE
        )
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: cannot sample {ntid}: {e}")
        rows = []
    for blob in rows:
        for name, value in zip(names, str(blob).split("\x1f")):
            samples[name].append(value)
    found = fields.index_like_fields(samples)
    _index_cache[ntid] = found
    return found


def _sound_files(values: dict, names) -> list:
    found = []
    for name in names:
        for match in fields._SOUND.finditer(values.get(name, "") or ""):
            filename = match.group(0)[len("[sound:"):-1].strip()
            if filename and filename not in found:
                found.append(filename)
    return found


def _entry(card) -> dict:
    """One card as a front and a back side, or None when it has no usable pair.

    Cloze note types are excluded outright. It is tempting to let them fall out
    on their own — question and answer render the same field, so the pair looks
    like it should collapse — but a cloze note type with an Extra field pairs
    the cloze text against Extra quite happily, and the "term" is then the raw
    `{{c1::…}}` source with the answer sitting in the middle of it. Anki's own
    reviewer is the only thing that renders those. Image Occlusion is a cloze
    note type as well, so this covers it too.
    """
    note_type = card.note_type()
    if int(note_type.get("type", 0)) == CLOZE:
        return None

    note = card.note()
    values = dict(note.items())
    template = card.template()
    ordinal = int(template.get("ord", card.ord))

    front_names = fields.template_fields(template.get("qfmt", ""))
    back_names = fields.template_fields(template.get("afmt", ""))

    pinned = get_store().field_map(int(note_type["id"]))
    front, back = fields.resolve(
        front_names, back_names, values, _index_fields(note_type), pinned
    )
    if not front or not back:
        return None

    # The reveal is the review screen's own card skin, built by the same
    # function — a study mode that dressed an answer differently from the
    # reviewer would be two designs of one thing, drifting apart.
    try:
        from . import card_skin

        skin = card_skin.answer_body(note, clean=fields.safe_html)
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: skin build failed: {e}")
        skin = ""

    return {
        "id": int(card.id),
        "front": _stack(front, values, front_names),
        "back": _stack(back, values, back_names),
        "skin": skin,
        "fieldFront": front,
        "fieldBack": back,
        "notetype": int(note_type["id"]),
        "ord": ordinal,
    }


def _stack(names, values: dict, template_names) -> dict:
    """One side of a card: its key field, then the rest as context.

    The **first** field is the side's key — what a typed answer is marked
    against, what a multiple choice offers, what a Match tile holds. Comparing
    a stack of fields against something the user typed has no good rule, so the
    stack is only ever *shown*.

    Audio comes from every field the *template* renders on this side, not from
    the chosen ones: a pronunciation lives in its own field, that field holds
    no words so it is never chosen, and scanning only the chosen fields is how
    the play button quietly disappeared once.
    """
    rows = []
    for name in names:
        markup = fields.safe_html(values.get(name, ""))
        if markup:
            rows.append({"label": name, "html": markup})
    key = names[0] if names else ""
    return {
        "key": key,
        "keyHtml": fields.safe_html(values.get(key, "")),
        "text": fields.plain_text(values.get(key, "")),
        "rows": rows,
        "audio": _sound_files(values, template_names),
    }


def _deck_card_ids(deck_id: int) -> list:
    """One unsuspended card per note, across the deck and its subdecks.

    By deck id rather than through `find_cards(f'deck:"{name}"')`: a deck name
    goes into a search term as a pattern, so a deck called "N5 *" would pull in
    half the collection and one containing a quote would not parse at all.
    `odid` is matched too, or a card lent to a filtered deck drops out of the
    deck it actually belongs to.

    **One card per note**, the lowest template ordinal. A note type with a
    forward and a reverse card gives Anki two cards to schedule separately,
    which is the point in the reviewer — but a study mode samples a pool and
    reverses the question with its own control, so both cards reaching it means
    every note appears twice, and Match can deal 勉強/べんきょう as one pair and
    べんきょう/勉強 as another.
    """
    try:
        deck_ids = mw.col.decks.deck_and_child_ids(deck_id)
        ids = ",".join(str(int(did)) for did in deck_ids)
        rows = mw.col.db.all(
            f"select nid, ord, id from cards "
            f"where (did in ({ids}) or odid in ({ids})) and queue != -1"
        )
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: cannot list deck cards: {e}")
        return []
    first = {}
    for nid, ordinal, card_id in rows:
        current = first.get(nid)
        if current is None or ordinal < current[0]:
            first[nid] = (ordinal, card_id)
    return [card_id for _ordinal, card_id in first.values()]


def _build_pool(card_ids) -> tuple:
    """(entries, skipped) for the given cards, in the order given."""
    entries, skipped = [], 0
    for card_id in card_ids:
        try:
            card = mw.col.get_card(card_id)
        except Exception:
            skipped += 1
            continue
        try:
            entry = _entry(card)
        except Exception as e:
            print(f"[Awesome Dashboard] quizlet: card {card_id} unreadable: {e}")
            entry = None
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    return entries, skipped


def _sample_pool(deck_id: int) -> tuple:
    """The pool for one visit: a saved session's cards, then a random sample.

    The sample is redrawn on every open, which is the point — a deck of 1300
    should not teach the same 400 terms forever. A resumed session's own cards
    have to be pinned into it, though: without that they are simply absent from
    the new pool and `prune` throws the session away as if the cards had been
    deleted.
    """
    card_ids = _deck_card_ids(deck_id)
    saved = get_store().session(deck_id) or {}
    available = set(card_ids)
    pinned = [int(cid) for cid in (saved.get("items") or []) if int(cid) in available]
    seen = set(pinned)
    rest = [cid for cid in card_ids if cid not in seen]
    rng = random.Random()
    order = qz.pick(len(rest), max(0, POOL_LIMIT - len(pinned)), rng)
    return _build_pool(pinned + [rest[position] for position in order])


# --- options ---------------------------------------------------------------


def _options() -> dict:
    config = conf.get()
    types = config.get(OPTION_KEYS["testTypes"]) or list(qz.DEFAULT_TEST_TYPES)
    if not isinstance(types, list):
        types = list(qz.DEFAULT_TEST_TYPES)
    types = [kind for kind in types if kind in qz.TEST_TYPES] \
        or list(qz.DEFAULT_TEST_TYPES)
    direction = config.get(OPTION_KEYS["direction"], "term")
    return {
        "direction": direction if direction in qz.DIRECTIONS else "term",
        "testLength": max(1, min(100, int(
            config.get(OPTION_KEYS["testLength"], qz.DEFAULT_TEST_LENGTH) or 20))),
        "testTypes": types,
        "matchPairs": max(2, min(qz.MAX_MATCH_PAIRS, int(
            config.get(OPTION_KEYS["matchPairs"], qz.DEFAULT_MATCH_PAIRS) or 6))),
        "sessionSize": max(0, min(POOL_LIMIT, int(
            config.get(OPTION_KEYS["sessionSize"], 40) or 0))),
        "grade": bool(config.get(OPTION_KEYS["grade"], False)),
    }


def _set_option(key: str, raw: str) -> None:
    if key not in OPTION_KEYS:
        return
    if key == "testTypes":
        value = [kind for kind in raw.split(",") if kind in qz.TEST_TYPES]
        if not value:
            return
    elif key == "direction":
        if raw not in qz.DIRECTIONS:
            return
        value = raw
    elif key == "grade":
        value = raw == "on"
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return
    conf.set_value(OPTION_KEYS[key], value)


# --- grading against the scheduler -----------------------------------------


def _maybe_grade(card_id: int, correct: bool) -> None:
    """Optionally pass the answer on to Anki's scheduler. Off by default.

    Only cards *already due* are touched. A study mode is not the reviewer:
    introducing a new card here would spend the deck's daily new allowance on
    a session the user thought was practice, and rescheduling a card that is
    not due would move a review the user never saw.

    `answer_card` on a modern scheduler takes a proto, not `(card, ease)`; the
    legacy `answerCard` is the two-argument door and is checked for rather than
    assumed, because a version without it must lose this option and nothing
    else.
    """
    if not _options()["grade"]:
        return
    try:
        if not mw.col.find_cards(f"cid:{int(card_id)} is:due"):
            return
        answer = getattr(mw.col.sched, "answerCard", None)
        if answer is None:
            return
        card = mw.col.get_card(card_id)
        card.start_timer()
        answer(card, 3 if correct else 1)
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: grading card {card_id} failed: {e}")


# --- session state ---------------------------------------------------------


def active() -> bool:
    return _active is not None


def close() -> None:
    global _active
    _active = None


def _deck_name(deck_id: int) -> str:
    try:
        return str(mw.col.decks.name(deck_id)).rsplit("::", 1)[-1]
    except Exception:
        return ""


def open_picker(deck_id: int) -> None:
    """Read the deck once and show the mode picker."""
    global _active
    entries, skipped = _sample_pool(deck_id)
    _active = {
        "deck": int(deck_id),
        "screen": "picker",
        "pool": entries,
        "byId": {entry["id"]: index for index, entry in enumerate(entries)},
        "skipped": skipped,
        "state": None,
    }
    _redraw()


def _redraw() -> None:
    """Re-render the overview webview with whatever `_active` now says.

    `_renderPage` rather than `refresh`: refresh runs the deck's card counts
    through a `QueryOp` and only draws in its callback, so a session screen
    would appear a beat late and behind a collection query it has no use for.
    Leaving a session goes through `refresh` instead — that page *is* the
    counts.
    """
    try:
        mw.overview._renderPage()
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: cannot draw overview: {e}")


# --- payloads --------------------------------------------------------------


def _pool_pair() -> dict:
    """The term/definition fields in play, for the picker's own line.

    Shown rather than assumed: the pair is a guess derived from the template,
    and a wrong guess the user can see before starting is a setting they can
    change, while a wrong guess they cannot see is a broken feature.

    The *commonest* pair, not the first card's. A note type with two templates
    has two pairs — a Japanese deck's forward card is word → reading and its
    reverse card is reading → word — so describing whichever card the sample
    happened to put first would show one of them at random, and the line would
    change between visits without anything having changed. `variants` is how
    many other pairs are in play, so a deck with more than one says so.
    """
    pool = _active["pool"]
    if not pool:
        return {}
    grouped = {}
    for entry in pool:
        key = (tuple(entry["fieldFront"]), tuple(entry["fieldBack"]))
        grouped.setdefault(key, []).append(entry)
    # Ties break on the field names so the line is stable across visits.
    (front, back), entries = max(
        grouped.items(), key=lambda item: (len(item[1]), item[0])
    )
    return {
        "term": ", ".join(front),
        "def": ", ".join(back),
        "sampleTerm": entries[0]["front"]["text"][:60],
        "sampleDef": entries[0]["back"]["text"][:60],
        "variants": len(grouped) - 1,
    }


def _resume() -> dict:
    stored = get_store().session(_active["deck"])
    if not isinstance(stored, dict) or stored.get("mode") != "learn":
        return None
    # Pruned on a copy: this only draws a banner, and `prune` rewrites the
    # session in place — doing that to the store's own dict would edit a
    # session the user has not chosen to resume.
    state = copy.deepcopy(stored)
    live = {entry["id"] for entry in _active["pool"]}
    qz.prune(state, live)
    if not state.get("items"):
        return None
    return {"mode": "learn", "progress": qz.progress(state)}


def _picker_payload() -> dict:
    record = get_store().record(_active["deck"])
    return {
        "screen": "picker",
        "deck": _deck_name(_active["deck"]),
        "total": len(_active["pool"]),
        "skipped": _active["skipped"],
        "pair": _pool_pair(),
        "record": record,
        "resume": _resume(),
        "options": _options(),
    }


def _card_types() -> list:
    """The note types the open deck actually uses, commonest first.

    Read from the pool rather than queried again: the pool was built from this
    deck's cards, so it already knows what is in play and in what proportion,
    and a note type with no usable pair has already dropped out.
    """
    grouped = {}
    for entry in _active["pool"]:
        grouped.setdefault(entry["notetype"], []).append(entry)
    return sorted(grouped.items(), key=lambda item: -len(item[1]))


def _setup_payload() -> dict:
    """The in-page settings screen: this deck's sides, and how a session runs.

    In the page rather than in the Qt dialog because every one of these is a
    property of *the session about to start*, and the page already knows which
    deck that is — the dialog had to grow a deck picker just to say what the
    screen it was opened from had already said. Only the two settings that are
    not about a session stayed behind: whether the feature appears at all, and
    whether it may touch the scheduler.
    """
    store = get_store()
    cards = []
    for notetype_id, entries in _card_types():
        note_type = mw.col.models.get(notetype_id) or {}
        first = entries[0]
        front, back = set(first["fieldFront"]), set(first["fieldBack"])
        cards.append({
            "nt": notetype_id,
            "label": str(note_type.get("name", "")),
            "count": len(entries),
            "pinned": bool(store.field_map(notetype_id)),
            "sample": {"front": first["front"]["text"][:60],
                       "back": first["back"]["text"][:60]},
            "fields": [
                {"name": str(field["name"]),
                 "front": str(field["name"]) in front,
                 "back": str(field["name"]) in back}
                for field in (note_type.get("flds") or [])
            ],
        })
    return {
        "screen": "setup",
        "deck": _deck_name(_active["deck"]),
        "maxFront": fields.MAX_FRONT,
        "maxBack": fields.MAX_BACK,
        "cards": cards,
        "options": _options(),
    }


def _set_field(payload: dict) -> None:
    """Tick or untick one field on one side of one card template."""
    try:
        notetype_id = int(payload["nt"])
        name, side = str(payload["field"]), str(payload["side"])
        on = bool(payload["on"])
    except (KeyError, TypeError, ValueError):
        return
    if side not in ("front", "back"):
        return

    current = None
    for candidate, entries in _card_types():
        if candidate == notetype_id:
            current = entries[0]
            break
    if current is None:
        return

    sides = {"front": list(current["fieldFront"]), "back": list(current["fieldBack"])}
    caps = {"front": fields.MAX_FRONT, "back": fields.MAX_BACK}
    other = "back" if side == "front" else "front"

    # Both rules are shown on the screen as a greyed-out box, so these are the
    # second line of defence rather than the message — a refusal the user
    # cannot see is a dead control.
    if on:
        if name not in sides[side]:
            if len(sides[side]) >= caps[side]:
                return
            sides[side].append(name)
        # A field cannot be the question and its own answer, so ticking it on
        # one side takes it off the other — unless it was the only thing there.
        # An empty side falls back to the automatic guess, so the tick would
        # appear to do nothing at all.
        if name in sides[other]:
            if len(sides[other]) <= 1:
                return
            sides[other] = [item for item in sides[other] if item != name]
    else:
        if len(sides[side]) <= 1:
            return
        sides[side] = [item for item in sides[side] if item != name]

    get_store().set_field_map(notetype_id, sides["front"], sides["back"])
    _reload_pool()


def _clear_field_map(payload: dict) -> None:
    try:
        notetype_id = int(payload["nt"])
    except (KeyError, TypeError, ValueError):
        return
    get_store().set_field_map(notetype_id, [], [])
    _reload_pool()


def _reload_pool() -> None:
    """Rebuild the pool against the new mapping and redraw the setup screen.

    The whole deck is read again rather than the changed entries patched: a
    field going on or off a side changes which cards have a usable pair at all,
    so the pool's membership moves, not just its contents.
    """
    get_store().flush()
    invalidate()
    entries, skipped = _sample_pool(_active["deck"])
    _active["pool"] = entries
    _active["byId"] = {entry["id"]: index for index, entry in enumerate(entries)}
    _active["skipped"] = skipped
    _send(_setup_payload())


def _entry_at(position: int) -> dict:
    pool = _active["pool"]
    return pool[position] if 0 <= position < len(pool) else {}


def _sides(entry: dict, direction: str) -> tuple:
    """(prompt, answer) halves of one card for a given direction.

    Each half carries the `side` its audio lives on rather than leaving the
    page to assume "prompt means front": with the direction reversed the
    prompt *is* the back, and playing the front's clip would give the answer
    away out loud.
    """
    front = dict(entry.get("front") or {}, side="front")
    back = dict(entry.get("back") or {}, side="back")
    return (back, front) if direction == "definition" else (front, back)


def _pool_position(state: dict, item: int) -> int:
    """Pool position of a session item, or -1 if its card is gone.

    Sessions hold card ids and the pool is rebuilt on every open, so the two
    are joined through the index built with the pool rather than by scanning
    it — a Learn round asks this once per option, per question.
    """
    items = state.get("items") or []
    if not 0 <= item < len(items):
        return -1
    return _active["byId"].get(int(items[item]), -1)


def _answer_strings(state: dict, direction: str) -> list:
    """The answer side of every item in the session, as plain text.

    Distractors are chosen from this and nothing else: options built from the
    whole pool could offer an answer the user has not been taught yet, and
    options built from HTML would compare markup instead of words.
    """
    values = []
    for item in range(len(state.get("items") or [])):
        position = _pool_position(state, item)
        entry = _entry_at(position) if position >= 0 else {}
        _, answer = _sides(entry, direction)
        values.append(answer["text"])
    return values


def _prompt_strings(state: dict, direction: str) -> list:
    values = []
    for item in range(len(state.get("items") or [])):
        position = _pool_position(state, item)
        entry = _entry_at(position) if position >= 0 else {}
        prompt, _ = _sides(entry, direction)
        values.append(prompt["text"])
    return values


def _learn_question(state: dict) -> dict:
    item = qz.next_item(state)
    if item is None:
        return None
    position = _pool_position(state, item)
    entry = _entry_at(position)
    direction = qz.direction_for(
        state.get("dir", "term"), item, grading.new_rng(state["seed"] + item)
    )
    prompt, answer = _sides(entry, direction)
    level = state["levels"][item]
    kind = qz.activity_for(level)
    question = {
        "kind": kind,
        "item": item,
        "cid": entry.get("id"),
        "level": level,
        "prompt": prompt,
        "skin": entry.get("skin") or "",
    }
    rng = grading.new_rng(state["seed"] * 31 + item * 7 + state.get("answered", 0))
    answers = _answer_strings(state, direction)

    if kind == "choice":
        options = grading.options_for(answers, item, qz.CHOICE_OPTIONS, rng)
        question["options"] = [_option_html(state, direction, o) for o in options]
        question["optionItems"] = options
    elif kind == "tf":
        truth = rng.random() < 0.5
        shown = item
        if not truth:
            wrong = grading.distractors(answers, item, 1, rng)
            if wrong:
                shown = wrong[0]
            else:
                truth = True
        question["shown"] = _option_html(state, direction, shown)
        question["truth"] = truth
    else:
        # Typed: the answer stays on this side of the bridge until it is
        # graded, so it cannot be read out of the page.
        question["hint"] = _hint(answer["text"])
        question["length"] = len(answer["text"])
    return question


def _option_html(state: dict, direction: str, item: int) -> dict:
    """One answer as an option: the key field only.

    The whole back stack would put a reading, a meaning and an example inside
    every button of a multiple choice — the option is the thing being chosen
    between, and the context belongs to the reveal that follows it.
    """
    position = _pool_position(state, item)
    entry = _entry_at(position)
    _, answer = _sides(entry, direction)
    return {"html": answer.get("keyHtml", ""), "text": answer.get("text", "")}


def _answer_side(state: dict, question: dict) -> dict:
    """The whole answer stack for a reveal, not just the key field.

    An option shows the key alone; the reveal shows everything the user chose
    to put on that side, which is the difference between "べんきょう" and the
    card they were actually studying.
    """
    item = question["item"]
    direction = qz.direction_for(
        state.get("dir", "term"), item, grading.new_rng(state["seed"] + item)
    )
    position = _pool_position(state, item)
    _, answer = _sides(_entry_at(position), direction)
    return answer


def _hint(text: str) -> str:
    """First letter of each word, the rest as dots."""
    parts = []
    for word in (text or "").split()[:6]:
        parts.append(word[0] + "·" * max(0, len(word) - 1))
    return " ".join(parts)


# Keys that decide the answer. They stay on this side of the bridge: a
# True/False question whose `truth` is in the page is a question the page can
# answer for you, and the same goes for which option index is the right one.
PRIVATE_KEYS = ("truth", "optionItems")


def _public(question: dict) -> dict:
    if not question:
        return question
    return {k: v for k, v in question.items() if k not in PRIVATE_KEYS}


def _learn_payload(feedback=None) -> dict:
    """(payload for the page, question with its answer still attached)."""
    state = _active["state"]
    payload = {
        "screen": "learn",
        "deck": _deck_name(_active["deck"]),
        "progress": qz.progress(state),
        "feedback": feedback,
    }
    if qz.finished(state):
        payload["screen"] = "learnDone"
        return payload, None
    if qz.round_done(state):
        payload["screen"] = "learnRound"
        return payload, None
    question = _learn_question(state)
    if question is None:
        payload["screen"] = "learnRound"
        return payload, None
    payload["question"] = _public(question)
    return payload, question


def _test_question(state: dict, index: int) -> dict:
    questions = state["questions"]
    if not 0 <= index < len(questions):
        return None
    spec = questions[index]
    item = spec["pos"]
    position = _pool_position(state, item)
    entry = _entry_at(position)
    prompt, _ = _sides(entry, spec["dir"])
    question = {
        "kind": spec["type"],
        "index": index,
        "total": len(questions),
        "cid": entry.get("id"),
        "prompt": prompt,
    }
    if spec["type"] == "choice":
        question["options"] = [
            _option_html(state, spec["dir"], option) for option in spec["options"]
        ]
    elif spec["type"] == "tf":
        question["shown"] = _option_html(state, spec["dir"], spec["shown"])
    return question


def _test_payload() -> dict:
    state = _active["state"]
    index = int(state.get("index", 0))
    if index >= len(state["questions"]):
        return _test_results()
    return {
        "screen": "test",
        "deck": _deck_name(_active["deck"]),
        "question": _test_question(state, index),
    }


def _test_results() -> dict:
    state = _active["state"]
    given = state.get("given") or {}
    result = qz.score(state["questions"], given)
    review = []
    for index, spec in enumerate(state["questions"]):
        answer = given.get(str(index)) or {}
        prompt_side = _option_html(state, _flip(spec["dir"]), spec["pos"])
        correct_side = _option_html(state, spec["dir"], spec["pos"])
        review.append({
            "prompt": prompt_side["text"],
            "expected": correct_side["text"],
            "given": answer.get("text", ""),
            "correct": bool(answer.get("correct")),
        })
    beaten = get_store().save_record(_active["deck"], "test", result["percent"])
    return {
        "screen": "testDone",
        "deck": _deck_name(_active["deck"]),
        "score": result,
        "review": review,
        "record": get_store().record(_active["deck"]),
        "beaten": beaten,
    }


def _flip(direction: str) -> str:
    return "definition" if direction == "term" else "term"


def _match_payload() -> dict:
    state = _active["state"]
    tiles = []
    for slot, item in enumerate(state["pairs"]):
        entry = _entry_at(item)
        prompt, answer = _sides(entry, state["dir"])
        tiles.append({"pair": slot, "side": "a", "html": prompt.get("keyHtml", "")})
        tiles.append({"pair": slot, "side": "b", "html": answer.get("keyHtml", "")})
    rng = grading.new_rng(state["seed"])
    rng.shuffle(tiles)
    return {
        "screen": "match",
        "deck": _deck_name(_active["deck"]),
        "tiles": tiles,
        "record": get_store().record(_active["deck"]).get("match"),
    }


def _cards_payload() -> dict:
    state = _active["state"]
    direction = state["dir"]
    cards = []
    for item in state["order"]:
        entry = _entry_at(item)
        prompt, answer = _sides(entry, direction)
        cards.append({
            "cid": entry.get("id"),
            "front": prompt,
            "back": answer,
            "skin": entry.get("skin") or "",
        })
    return {
        "screen": "cards",
        "deck": _deck_name(_active["deck"]),
        "cards": cards,
        "index": int(state.get("index", 0)),
    }


def _payload() -> dict:
    if _active is None:
        return {"screen": "picker"}
    screen = _active["screen"]
    if not _active["pool"]:
        return {
            "screen": "empty",
            "deck": _deck_name(_active["deck"]),
            "skipped": _active["skipped"],
        }
    if screen == "picker":
        return _picker_payload()
    if screen == "setup":
        return _setup_payload()
    if screen == "cards":
        return _cards_payload()
    if screen == "learn":
        payload, question = _learn_payload()
        _active["question"] = question
        return payload
    if screen == "test":
        return _test_payload()
    if screen == "match":
        return _match_payload()
    return _picker_payload()


# --- starting a mode -------------------------------------------------------


def _new_seed() -> int:
    return int(time.time() * 1000) % 2147483647


def _session_items(size: int) -> list:
    pool = _active["pool"]
    rng = random.Random()
    order = qz.pick(len(pool), size, rng)
    return [pool[position]["id"] for position in order]


def start(mode: str, resume: bool = False) -> None:
    if _active is None or mode not in MODES:
        return
    options = _options()
    pool = _active["pool"]
    if not pool:
        return
    store = get_store()

    if mode == "cards":
        rng = random.Random()
        _active["state"] = {
            "dir": options["direction"] if options["direction"] != "mixed" else "term",
            "order": qz.pick(len(pool), 0, rng),
            "index": 0,
        }
    elif mode == "learn":
        state = store.session(_active["deck"]) if resume else None
        if isinstance(state, dict) and state.get("mode") == "learn":
            qz.prune(state, [entry["id"] for entry in pool])
        else:
            state = qz.start_learn(
                _session_items(options["sessionSize"]),
                _new_seed(), options["direction"],
            )
        if not state.get("queue") and not qz.finished(state):
            qz.start_round(state)
        _active["state"] = state
        store.save_session(_active["deck"], state)
    elif mode == "test":
        seed = _new_seed()
        items = _session_items(0)
        state = {
            "mode": "test", "seed": seed, "dir": options["direction"],
            "items": items, "index": 0, "given": {},
        }
        _active["state"] = state
        state["questions"] = qz.build_test(
            _prompt_strings(state, options["direction"]),
            _answer_strings(state, options["direction"]),
            options["testLength"], options["testTypes"],
            options["direction"], seed,
        )
    elif mode == "match":
        _active["state"] = {
            "mode": "match",
            "seed": _new_seed(),
            "dir": options["direction"] if options["direction"] != "mixed" else "term",
            "pairs": qz.match_pairs(len(pool), options["matchPairs"], _new_seed()),
        }

    _active["screen"] = mode
    _redraw()


# --- answers ---------------------------------------------------------------


def _grade_learn(question: dict, given: dict, state: dict) -> dict:
    """(correct, exact, expected text) for one Learn answer."""
    item = question["item"]
    direction = qz.direction_for(
        state.get("dir", "term"), item, grading.new_rng(state["seed"] + item)
    )
    expected = _option_html(state, direction, item)
    kind = question["kind"]

    if kind == "typed":
        typed = str(given.get("text", ""))
        correct, exact = grading.check_typed(typed, expected["text"])
        if given.get("skip"):
            correct, exact = False, False
        return {"correct": correct, "exact": exact, "expected": expected,
                "given": typed}
    if kind == "tf":
        said = bool(given.get("value"))
        correct = said == bool(question["truth"])
        return {"correct": correct, "exact": correct, "expected": expected,
                "given": ""}
    chosen = given.get("index")
    options = question.get("optionItems") or []
    correct = isinstance(chosen, int) and 0 <= chosen < len(options) \
        and options[chosen] == item
    given_text = ""
    if isinstance(chosen, int) and 0 <= chosen < len(options):
        given_text = _option_html(state, direction, options[chosen])["text"]
    return {"correct": correct, "exact": correct, "expected": expected,
            "given": given_text}


def _answer_learn(given: dict) -> None:
    state = _active["state"]
    question = _active.get("question")
    if not question:
        return
    result = _grade_learn(question, given, state)
    _maybe_grade(question.get("cid"), result["correct"])
    qz.apply_answer(state, question["item"], result["correct"])
    get_store().save_session(_active["deck"], state)

    payload, upcoming = _learn_payload(feedback={
        "correct": result["correct"],
        "exact": result["exact"],
        "expected": result["expected"],
        "given": result["given"],
        "answer": _answer_side(state, question),
        "skin": question.get("skin") or "",
    })
    _active["question"] = upcoming
    _send(payload)


def _answer_test(given: dict) -> None:
    state = _active["state"]
    index = int(state.get("index", 0))
    questions = state["questions"]
    if not 0 <= index < len(questions):
        return
    spec = questions[index]
    item = spec["pos"]
    expected = _option_html(state, spec["dir"], item)

    if spec["type"] == "typed":
        typed = str(given.get("text", ""))
        correct, _ = grading.check_typed(typed, expected["text"])
        text = typed
    elif spec["type"] == "tf":
        correct = bool(given.get("value")) == bool(spec["truth"])
        text = tr("qz_true") if given.get("value") else tr("qz_false")
    else:
        chosen = given.get("index")
        options = spec.get("options") or []
        correct = isinstance(chosen, int) and 0 <= chosen < len(options) \
            and options[chosen] == item
        text = ""
        if isinstance(chosen, int) and 0 <= chosen < len(options):
            text = _option_html(state, spec["dir"], options[chosen])["text"]

    state.setdefault("given", {})[str(index)] = {"correct": correct, "text": text}
    _maybe_grade(_entry_at(_pool_position(state, item)).get("id"), correct)
    state["index"] = index + 1
    _send(_test_payload())


def _send(payload: dict) -> None:
    try:
        blob = json.dumps(payload, ensure_ascii=False)
        mw.overview.web.eval(f"window.AwdQz && AwdQz.apply({blob});")
    except Exception as e:
        print(f"[Awesome Dashboard] quizlet: send failed: {e}")


# --- rendering -------------------------------------------------------------


def _strings() -> dict:
    """Every label the page draws, written out one literal at a time.

    A comprehension over a tuple of key names would be shorter and would make
    `tools/check_locales.py` blind to all of them at once — it only matches a
    literal key inside a tr call, which is exactly what stops a renamed or
    misspelled key from shipping as an empty label.
    """
    return {
        "qz_title": tr("qz_title"),
        "qz_back": tr("qz_back"),
        "qz_exit": tr("qz_exit"),
        "qz_settings": tr("qz_settings"),
        "qz_change": tr("qz_change"),
        "qz_cards": tr("qz_cards"),
        "qz_learn": tr("qz_learn"),
        "qz_test": tr("qz_test"),
        "qz_match": tr("qz_match"),
        "qz_cards_desc": tr("qz_cards_desc"),
        "qz_learn_desc": tr("qz_learn_desc"),
        "qz_test_desc": tr("qz_test_desc"),
        "qz_match_desc": tr("qz_match_desc"),
        "qz_terms": tr("qz_terms"),
        "qz_skipped": tr("qz_skipped"),
        "qz_pair_label": tr("qz_pair_label"),
        "qz_pair_more": tr("qz_pair_more"),
        "qz_details": tr("qz_details"),
        "qz_field": tr("qz_field"),
        "qz_other_types": tr("qz_other_types"),
        "qz_fieldmap_desc": tr("qz_fieldmap_desc"),
        "qz_length": tr("qz_length"),
        "qz_pairs": tr("qz_pairs"),
        "qz_reset_auto": tr("qz_reset_auto"),
        "qz_session_size": tr("qz_session_size"),
        "qz_side_back": tr("qz_side_back"),
        "qz_side_front": tr("qz_side_front"),
        "qz_side_max": tr("qz_side_max"),
        "qz_sizes": tr("qz_sizes"),
        "qz_type_choice": tr("qz_type_choice"),
        "qz_type_tf": tr("qz_type_tf"),
        "qz_type_typed": tr("qz_type_typed"),
        "qz_types_hint": tr("qz_types_hint"),
        "qz_whole_deck": tr("qz_whole_deck"),
        "qz_empty_title": tr("qz_empty_title"),
        "qz_empty_body": tr("qz_empty_body"),
        "qz_resume": tr("qz_resume"),
        "qz_resume_body": tr("qz_resume_body"),
        "qz_restart": tr("qz_restart"),
        "qz_start": tr("qz_start"),
        "qz_flip": tr("qz_flip"),
        "qz_shuffle": tr("qz_shuffle"),
        "qz_of": tr("qz_of"),
        "qz_round": tr("qz_round"),
        "qz_round_done": tr("qz_round_done"),
        "qz_round_done_body": tr("qz_round_done_body"),
        "qz_continue": tr("qz_continue"),
        "qz_learn_done": tr("qz_learn_done"),
        "qz_learn_done_body": tr("qz_learn_done_body"),
        "qz_tf_prompt": tr("qz_tf_prompt"),
        "qz_true": tr("qz_true"),
        "qz_false": tr("qz_false"),
        "qz_type_prompt": tr("qz_type_prompt"),
        "qz_dont_know": tr("qz_dont_know"),
        "qz_hint": tr("qz_hint"),
        "qz_submit": tr("qz_submit"),
        "qz_correct": tr("qz_correct"),
        "qz_incorrect": tr("qz_incorrect"),
        "qz_almost": tr("qz_almost"),
        "qz_answer_was": tr("qz_answer_was"),
        "qz_your_answer": tr("qz_your_answer"),
        "qz_question": tr("qz_question"),
        "qz_streak": tr("qz_streak"),
        "qz_test_done": tr("qz_test_done"),
        "qz_score": tr("qz_score"),
        "qz_review": tr("qz_review"),
        "qz_match_intro": tr("qz_match_intro"),
        "qz_match_done": tr("qz_match_done"),
        "qz_best": tr("qz_best"),
        "qz_new_record": tr("qz_new_record"),
        "qz_again": tr("qz_again"),
        "qz_mastered": tr("qz_mastered"),
        "qz_direction": tr("qz_direction"),
        "qz_dir_term": tr("qz_dir_term"),
        "qz_dir_def": tr("qz_dir_def"),
        "qz_dir_mixed": tr("qz_dir_mixed"),
        "qz_play": tr("qz_play"),
    }


def render(overview) -> None:
    """Draw the active session. Called from `screens/overview.render_page`."""
    blob = json.dumps(_payload(), ensure_ascii=False)
    strings = json.dumps(_strings(), ensure_ascii=False)
    # The first payload rides in the body rather than going through `eval`,
    # which queues until the page posts `domDone` — a page that has to wait for
    # that to draw anything at all has "blank" as one of its states.
    body = f"""
    <div class="awd-qz" id="awd-qz"></div>
    <script>
      window.AWD_QZ_I18N = {strings};
      window.AWD_QZ = {blob};
      if (window.AwdQz) AwdQz.mount();
    </script>
    """
    overview.web.stdHtml(body=body, css=[], js=[], context=overview)
    from . import dashboard

    dashboard.apply_bar_visibility("overview")


def button_html(deck_id: int) -> str:
    """The "Study modes" entry on the normal overview page."""
    return (
        f'<button class="awd-ov-modes" onclick="pycmd(\'awd:qz:open:{int(deck_id)}\')">'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="3" y="5" width="13" height="10" rx="2"/>'
        '<path d="M8 19h13V9"/></svg>'
        f'<span>{html.escape(tr("qz_title"))}</span></button>'
    )


# --- bridge ----------------------------------------------------------------


def _play(raw: str) -> None:
    """`<card id>:<side>` — the sound files that side of the card renders."""
    parts = raw.split(":")
    if len(parts) != 2 or _active is None:
        return
    try:
        card_id = int(parts[0])
    except (TypeError, ValueError):
        return
    key = "audioDef" if parts[1] == "back" else "audioTerm"
    for entry in _active["pool"]:
        if entry["id"] != card_id:
            continue
        from . import card_skin

        for filename in entry.get(key) or []:
            card_skin.play_file(filename)
        return


def command(rest: str) -> None:
    """Everything under `awd:qz:`."""
    global _active

    if rest.startswith("open:"):
        try:
            open_picker(int(rest[len("open:"):]))
        except (TypeError, ValueError):
            pass
        return
    if _active is None:
        return

    if rest == "exit":
        close()
        try:
            mw.overview.refresh()
        except Exception as e:
            print(f"[Awesome Dashboard] quizlet: cannot leave modes: {e}")
    elif rest == "picker":
        _active["screen"] = "picker"
        _active["state"] = None
        _redraw()
    elif rest.startswith("start:"):
        parts = rest[len("start:"):].split(":")
        start(parts[0], resume=len(parts) > 1 and parts[1] == "resume")
    elif rest == "restart":
        get_store().clear_session(_active["deck"])
        start("learn")
    elif rest == "round":
        qz.start_round(_active["state"])
        get_store().save_session(_active["deck"], _active["state"])
        payload, upcoming = _learn_payload()
        _active["question"] = upcoming
        _send(payload)
    elif rest.startswith("answer:"):
        try:
            given = json.loads(rest[len("answer:"):])
        except Exception as e:
            print(f"[Awesome Dashboard] quizlet: answer unreadable: {e}")
            return
        if _active["screen"] == "learn":
            _answer_learn(given)
        elif _active["screen"] == "test":
            _answer_test(given)
    elif rest.startswith("index:"):
        # Flashcards keep their own position; this only records it so the
        # screen can be redrawn where the user left it.
        try:
            _active["state"]["index"] = int(rest[len("index:"):])
        except (TypeError, ValueError, KeyError):
            pass
    elif rest.startswith("match:"):
        try:
            seconds = float(rest[len("match:"):])
        except (TypeError, ValueError):
            return
        beaten = get_store().save_record(_active["deck"], "match", seconds)
        _send({
            "screen": "matchDone",
            "deck": _deck_name(_active["deck"]),
            "seconds": round(seconds, 1),
            "beaten": beaten,
            "record": get_store().record(_active["deck"]).get("match"),
        })
    elif rest.startswith("opt:"):
        # No payload back: the page has already moved the control, and a redraw
        # would rebuild the sliding pill at its destination with the animation
        # skipped. Persisting is all that is left to do.
        parts = rest[len("opt:"):].split(":", 1)
        if len(parts) == 2:
            _set_option(parts[0], parts[1])
    elif rest.startswith("play:"):
        _play(rest[len("play:"):])
    elif rest == "setup":
        _active["screen"] = "setup"
        _active["state"] = None
        _send(_setup_payload())
    elif rest.startswith("field:"):
        try:
            _set_field(json.loads(rest[len("field:"):]))
        except Exception as e:
            print(f"[Awesome Dashboard] quizlet: field toggle failed: {e}")
    elif rest.startswith("fieldauto:"):
        try:
            _clear_field_map(json.loads(rest[len("fieldauto:"):]))
        except Exception as e:
            print(f"[Awesome Dashboard] quizlet: field reset failed: {e}")
    elif rest == "reload":
        open_picker(_active["deck"])


def install_hooks() -> None:
    """Leave the overview and the session is over.

    The screen lives in the overview's webview, so anything that navigates away
    has already destroyed it; keeping `_active` set would put the user back
    inside a half-finished round the next time they opened *any* deck.
    """
    from aqt import gui_hooks

    def on_state(new_state, *_args):
        if new_state != "overview":
            close()

    def on_notes_change(*_args):
        invalidate()

    gui_hooks.state_did_change.append(on_state)
    hook = getattr(gui_hooks, "operation_did_execute", None)
    if hook is not None:
        hook.append(on_notes_change)
