#!/usr/bin/env python3
"""Quizlet study-mode tests — run from the add-on root:

    python3 tools/test_quizlet.py

`features/quizlet/{fields,grading,session}` never import `aqt`, so they load
directly under a synthetic package name. Keep it that way; `store.py` and
`screens/quizlet.py` are where anything needing Anki belongs.
"""

import importlib.util
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = "awd_quizlet"

_package = types.ModuleType(PACKAGE)
_package.__path__ = [str(ROOT / "features" / "quizlet")]
sys.modules[PACKAGE] = _package


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / "features" / "quizlet" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PACKAGE}.{name}"] = module
    spec.loader.exec_module(module)
    return module


fields = _load("fields")
grading = _load("grading")
session = _load("session")
# store.py may import `aqt`, but only inside methods, so the pin reader loads
# here too — and it is the one piece of it with rules worth testing.
store = _load("store")


# The note type this feature was built against: a Japanese vocabulary deck
# whose *first* field is a row number. Picking fields by position gives a term
# of "1487" and a definition of the word, which is the bug that started this.
JP_FRONT = """
<div style='font-size: 20px;'>{{audio}}</div>
<div style='font-size: 100px;'>{{tu vung}}</div>
<div style='font-size: 20px;'>{{stt}}</div>
"""
JP_BACK = """
<div>{{cach doc}}</div>
<div>{{am han}}</div>
<div>{{image}}</div>
<div>{{nghia}}</div>
<div>{{vd}}</div>
<div>{{bonus}}</div>
"""
# The reverse template: the row number comes *before* the real prompt, so
# "first field on the front" is not enough on its own either.
JP_REVERSE_FRONT = """
<div>{{audio}}</div>
<div>{{stt}}</div>
<div>{{cach doc}}</div>
"""
JP_REVERSE_BACK = """
<div style='font-size: 100px;'>{{tu vung}}</div>
<div>{{am han}}</div>
<div>{{image}}</div>
<div>{{nghia}}</div>
"""

JP_NOTE = {
    "stt": "1487",
    "tu vung": "勉強",
    "cach doc": "べんきょう",
    "am han": "MIỄN CƯỜNG",
    "vd": "毎日日本語を勉強します。",
    "image": '<img src="benkyou.jpg">',
    "nghia": "học tập, sự học",
    "bonus": "",
    "audio": "[sound:benkyou.mp3]",
}

# Enough notes for the index detector to have something to say.
JP_SAMPLES = {
    "stt": [str(n) for n in range(1400, 1420)],
    "tu vung": [f"単語{n}" for n in range(20)],
    "cach doc": [f"たんご{n}" for n in range(20)],
    "nghia": [f"nghĩa {n}" for n in range(20)],
    "audio": [f"[sound:{n}.mp3]" for n in range(20)],
    # A level field: numeric, but the same handful of values over and over.
    "level": ["1", "2", "3"] * 7,
}


class TemplateParseTests(unittest.TestCase):
    def test_fields_in_render_order(self):
        self.assertEqual(fields.template_fields(JP_FRONT),
                         ["audio", "tu vung", "stt"])

    def test_specials_are_not_fields(self):
        fmt = "{{FrontSide}}<hr id=answer>{{Tags}}{{Deck}}{{Card}}{{Back}}"
        self.assertEqual(fields.template_fields(fmt), ["Back"])

    def test_filters_are_stripped(self):
        fmt = "{{type:Front}}{{furigana:Reading}}{{text:furigana:Reading}}"
        self.assertEqual(fields.template_fields(fmt), ["Front", "Reading"])

    def test_conditionals_contribute_the_field_not_the_condition(self):
        fmt = "{{#Image}}{{Image}}{{/Image}}{{^Audio}}no audio{{/Audio}}"
        self.assertEqual(fields.template_fields(fmt), ["Image"])

    def test_duplicates_collapse(self):
        self.assertEqual(fields.template_fields("{{A}}{{A}}{{B}}"), ["A", "B"])

    def test_empty_template(self):
        self.assertEqual(fields.template_fields(""), [])
        self.assertEqual(fields.template_fields("{{}}"), [])


class PlainTextTests(unittest.TestCase):
    def test_sound_tags_are_not_words(self):
        self.assertEqual(fields.plain_text("[sound:a.mp3]"), "")
        self.assertTrue(fields.is_media_only("[sound:a.mp3]"))

    def test_an_image_alone_is_media_only(self):
        self.assertTrue(fields.is_media_only('<img src="x.png">'))

    def test_an_image_with_a_caption_is_not(self):
        self.assertFalse(fields.is_media_only('<img src="x.png">a house'))

    def test_style_blocks_are_dropped_whole(self):
        self.assertEqual(fields.plain_text("<style>.a{color:red}</style>hi"), "hi")

    def test_entities_and_breaks(self):
        self.assertEqual(fields.plain_text("a&nbsp;b<br>c&amp;d"), "a b c&d")

    def test_nbsp_is_not_text(self):
        self.assertFalse(fields.has_text("&nbsp; &#160;"))


class IndexFieldTests(unittest.TestCase):
    def test_a_row_number_is_detected(self):
        self.assertIn("stt", fields.index_like_fields(JP_SAMPLES))

    def test_a_repeating_level_field_is_not(self):
        self.assertNotIn("level", fields.index_like_fields(JP_SAMPLES))

    def test_words_are_not(self):
        flagged = fields.index_like_fields(JP_SAMPLES)
        self.assertNotIn("tu vung", flagged)
        self.assertNotIn("nghia", flagged)

    def test_a_tiny_sample_is_left_alone(self):
        # Three notes cannot tell an index from a coincidence.
        self.assertEqual(fields.index_like_fields({"n": ["1", "2", "3"]}), set())


class ChooseTests(unittest.TestCase):
    """The bug this feature exists to not repeat."""

    def setUp(self):
        self.index = fields.index_like_fields(JP_SAMPLES)

    def test_forward_card_is_word_to_meaning(self):
        term, definition = fields.choose(
            fields.template_fields(JP_FRONT),
            fields.template_fields(JP_BACK),
            JP_NOTE, self.index,
        )
        self.assertEqual(term, "tu vung")
        self.assertNotEqual(term, "stt")
        self.assertEqual(definition, "cach doc")

    def test_the_reverse_card_is_a_different_pair(self):
        term, definition = fields.choose(
            fields.template_fields(JP_REVERSE_FRONT),
            fields.template_fields(JP_REVERSE_BACK),
            JP_NOTE, self.index,
        )
        # Picking by field position would give ("stt", "tu vung") for both
        # templates; the ordinal has to change the answer.
        self.assertEqual(term, "cach doc")
        self.assertEqual(definition, "tu vung")

    def test_audio_alone_is_never_the_term(self):
        term, _ = fields.choose(["audio"], ["nghia"], JP_NOTE, self.index)
        self.assertIsNone(term)

    def test_an_empty_field_is_skipped(self):
        term, definition = fields.choose(
            ["tu vung"], ["bonus", "nghia"], JP_NOTE, self.index
        )
        self.assertEqual(definition, "nghia")
        self.assertEqual(term, "tu vung")

    def test_an_all_numeric_note_type_still_gets_a_pair(self):
        # Better a wrong-looking pair the picker can show than no session.
        note = {"stt": "12", "no": "34"}
        term, definition = fields.choose(["stt"], ["no"], note, {"stt", "no"})
        self.assertEqual((term, definition), ("stt", "no"))

    def test_the_term_is_never_also_the_definition(self):
        note = {"A": "x"}
        term, definition = fields.choose(["A"], ["A"], note, set())
        self.assertEqual(term, "A")
        self.assertIsNone(definition)


class ResolveTests(unittest.TestCase):
    """A side is a set of fields; the first one is what gets asked."""

    def setUp(self):
        self.index = fields.index_like_fields(JP_SAMPLES)
        self.front = fields.template_fields(JP_FRONT)
        self.back = fields.template_fields(JP_BACK)

    def resolve(self, pinned=None):
        return fields.resolve(self.front, self.back, JP_NOTE, self.index, pinned)

    def test_no_pin_is_the_single_field_guess(self):
        self.assertEqual(self.resolve(), (["tu vung"], ["cach doc"]))

    def test_a_pin_can_hold_several_fields(self):
        front, back = self.resolve({"front": ["tu vung"],
                                    "back": ["nghia", "vd", "cach doc"]})
        self.assertEqual(front, ["tu vung"])
        self.assertEqual(back, ["nghia", "vd", "cach doc"])

    def test_the_pinned_order_is_kept(self):
        # The first field is the one being asked, so reordering is a setting.
        _, back = self.resolve({"front": ["tu vung"], "back": ["vd", "nghia"]})
        self.assertEqual(back[0], "vd")

    def test_a_side_the_pin_does_not_name_falls_back_to_the_guess(self):
        front, back = self.resolve({"back": ["nghia"]})
        self.assertEqual(front, ["tu vung"])
        self.assertEqual(back, ["nghia"])

    def test_a_field_on_both_sides_is_dropped_from_the_back(self):
        # Otherwise the question shows its own answer.
        front, back = self.resolve({"front": ["tu vung", "nghia"],
                                    "back": ["nghia", "vd"]})
        self.assertEqual(front, ["tu vung", "nghia"])
        self.assertEqual(back, ["vd"])

    def test_a_pinned_field_the_note_type_lost_is_ignored(self):
        front, back = self.resolve({"front": ["renamed"], "back": ["nghia"]})
        self.assertEqual(front, ["tu vung"])
        self.assertEqual(back, ["nghia"])

    def test_each_side_is_capped(self):
        front, back = self.resolve({
            "front": ["tu vung", "cach doc", "am han", "stt"],
            "back": ["nghia", "vd", "bonus", "am han", "image"],
        })
        self.assertEqual(len(front), fields.MAX_FRONT)
        self.assertEqual(len(back), fields.MAX_BACK)

    def test_the_cap_keeps_the_first_fields_the_user_picked(self):
        front, _ = self.resolve({"front": ["cach doc", "tu vung", "am han"],
                                 "back": ["nghia"]})
        self.assertEqual(front, ["cach doc", "tu vung"])

    def test_a_field_pushed_off_the_front_may_be_the_answer(self):
        # Truncating the front before clearing the overlap, not after.
        front, back = self.resolve({"front": ["tu vung", "cach doc", "nghia"],
                                    "back": ["nghia", "vd"]})
        self.assertEqual(front, ["tu vung", "cach doc"])
        self.assertEqual(back, ["nghia", "vd"])

    def test_an_empty_pin_falls_back_rather_than_showing_nothing(self):
        self.assertEqual(self.resolve({"front": [], "back": []}),
                         (["tu vung"], ["cach doc"]))


class PinShapeTests(unittest.TestCase):
    """`awd_qz_fieldmap` has had three shapes; all of them still read."""

    def test_the_current_shape(self):
        self.assertEqual(
            store._sides({"front": ["A"], "back": ["B", "C"]}),
            {"front": ["A"], "back": ["B", "C"]},
        )

    def test_the_one_field_a_side_shape(self):
        self.assertEqual(store._sides({"term": "A", "def": "B"}),
                         {"front": ["A"], "back": ["B"]})

    def test_the_per_card_template_shape_collapses_to_the_first(self):
        pinned = {"1": {"front": ["B"], "back": ["A"]},
                  "0": {"front": ["A"], "back": ["B"]}}
        self.assertEqual(store._sides(pinned),
                         {"front": ["A"], "back": ["B"]})

    def test_a_side_the_pin_does_not_name_stays_absent(self):
        # Absent means "guess it"; an empty list would mean "show nothing".
        self.assertEqual(store._sides({"back": ["B"]}), {"back": ["B"]})

    def test_junk(self):
        self.assertEqual(store._sides({}), {})
        self.assertEqual(store._sides(None), {})
        self.assertEqual(store._sides({"0": "nonsense"}), {})


class ClozeShapeTests(unittest.TestCase):
    """Why cloze is excluded by note type and not by how its fields look.

    The tempting shortcut is to let cloze fall out on its own, on the grounds
    that its question and answer render the same field so the pair collapses.
    These are the two shapes that shortcut gets wrong, and they are why
    `screens/quizlet.py` checks the note type instead.
    """

    def test_a_bare_cloze_does_collapse(self):
        front = fields.template_fields("{{cloze:Text}}")
        back = fields.template_fields("{{cloze:Text}}")
        term, definition = fields.choose(front, back, {"Text": "a {{c1::b}} c"}, set())
        self.assertEqual(term, "Text")
        self.assertIsNone(definition)

    def test_but_an_extra_field_makes_it_look_usable(self):
        front = fields.template_fields("{{cloze:Text}}")
        back = fields.template_fields("{{cloze:Text}}{{Extra}}")
        term, definition = fields.choose(
            front, back, {"Text": "a {{c1::b}} c", "Extra": "a note"}, set()
        )
        # A perfectly ordinary looking pair whose "term" is raw cloze source
        # with the answer written in the middle of it.
        self.assertEqual((term, definition), ("Text", "Extra"))
        self.assertIn("c1::", fields.plain_text({"Text": "a {{c1::b}} c"}["Text"]))


class SafeHtmlTests(unittest.TestCase):
    """Field markup goes into the page inside a JSON payload, so it is filtered
    rather than trusted — most note fields were pasted in from a web page."""

    def test_scripts_go_with_their_contents(self):
        self.assertEqual(fields.safe_html("<script>alert(1)</script>hi"), "hi")

    def test_style_blocks_go_too(self):
        self.assertEqual(fields.safe_html("<style>b{color:red}</style>x"), "x")

    def test_event_handlers_are_dropped(self):
        self.assertEqual(fields.safe_html('<b onclick="x()">hi</b>'), "<b>hi</b>")

    def test_inline_styling_is_dropped_but_the_text_is_kept(self):
        self.assertEqual(
            fields.safe_html('<div style="color:#fff" class="x">word</div>'),
            "<div>word</div>",
        )

    def test_formatting_and_ruby_survive(self):
        self.assertEqual(
            fields.safe_html("<b>a</b><ruby>漢<rt>かん</rt></ruby>"),
            "<b>a</b><ruby>漢<rt>かん</rt></ruby>",
        )

    def test_images_keep_their_source(self):
        self.assertEqual(fields.safe_html('<img src="a.png" style="w">'),
                         '<img src="a.png"/>')

    def test_sound_tags_are_removed(self):
        self.assertEqual(fields.safe_html("word [sound:a.mp3]"), "word")

    def test_stray_angle_brackets_are_escaped(self):
        self.assertEqual(fields.safe_html("a < b & c"), "a &lt; b &amp; c")


class TypedAnswerTests(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(grading.check_typed("học tập", "học tập"), (True, True))

    def test_case_and_accents_fold(self):
        self.assertEqual(grading.check_typed("HOC TAP", "học tập"), (True, True))

    def test_a_typo_passes_but_is_not_exact(self):
        correct, exact = grading.check_typed("recieve", "receive")
        self.assertTrue(correct)
        self.assertFalse(exact)

    def test_a_different_short_word_fails(self):
        self.assertEqual(grading.check_typed("cat", "car")[0], False)

    def test_one_synonym_out_of_several_counts(self):
        self.assertTrue(grading.check_typed("to study", "to study, to learn")[0])

    def test_empty_is_never_right(self):
        self.assertEqual(grading.check_typed("", "anything"), (False, False))
        self.assertEqual(grading.check_typed("   ", "anything"), (False, False))

    def test_punctuation_only_differences(self):
        self.assertTrue(grading.check_typed("to go.", "to go")[0])


class DistractorTests(unittest.TestCase):
    def setUp(self):
        self.rng = grading.new_rng(7)

    def test_the_answer_is_never_a_distractor(self):
        pool = ["a", "b", "c", "d", "e"]
        for _ in range(20):
            self.assertNotIn(0, grading.distractors(pool, 0, 3, self.rng))

    def test_a_duplicate_meaning_is_not_offered(self):
        pool = ["to go", "to go", "to eat", "to sleep"]
        self.assertNotIn(1, grading.distractors(pool, 0, 3, self.rng))

    def test_options_always_include_the_answer(self):
        pool = [f"m{n}" for n in range(10)]
        options = grading.options_for(pool, 3, 4, self.rng)
        self.assertIn(3, options)
        self.assertEqual(len(options), 4)
        self.assertEqual(len(set(options)), 4)

    def test_a_two_card_deck_degrades_instead_of_failing(self):
        options = grading.options_for(["a", "b"], 0, 4, self.rng)
        self.assertIn(0, options)
        self.assertLessEqual(len(options), 2)

    def test_a_one_card_deck_offers_only_the_answer(self):
        self.assertEqual(grading.options_for(["a"], 0, 4, self.rng), [0])


class LearnTests(unittest.TestCase):
    def setUp(self):
        self.state = session.start_learn(list(range(100, 110)), seed=1)
        session.start_round(self.state)

    def _answer_all_correct(self, times: int):
        for _ in range(times):
            while True:
                position = session.next_item(self.state)
                if position is None:
                    break
                session.apply_answer(self.state, position, True)
            if not session.finished(self.state):
                session.start_round(self.state)

    def test_a_round_is_capped(self):
        self.assertEqual(len(self.state["queue"]), session.ROUND_SIZE)

    def test_activity_climbs_with_the_level(self):
        self.assertEqual(session.activity_for(0), "tf")
        self.assertEqual(session.activity_for(1), "choice")
        self.assertEqual(session.activity_for(2), "typed")

    def test_a_correct_answer_leaves_the_queue(self):
        position = session.next_item(self.state)
        session.apply_answer(self.state, position, True)
        self.assertNotIn(position, self.state["queue"])
        self.assertEqual(self.state["levels"][position], 1)

    def test_a_miss_comes_back_once_and_then_waits(self):
        position = session.next_item(self.state)
        session.apply_answer(self.state, position, False)
        self.assertIn(position, self.state["queue"])
        # Drain everything else, then miss it again.
        while session.next_item(self.state) != position:
            session.apply_answer(self.state, session.next_item(self.state), True)
        session.apply_answer(self.state, position, False)
        self.assertNotIn(position, self.state["queue"])

    def test_a_miss_never_goes_below_zero(self):
        position = session.next_item(self.state)
        for _ in range(5):
            session.apply_answer(self.state, position, False)
        self.assertEqual(self.state["levels"][position], 0)

    def test_streak_resets_on_a_miss_and_best_is_kept(self):
        for _ in range(3):
            session.apply_answer(self.state, session.next_item(self.state), True)
        self.assertEqual(self.state["streak"], 3)
        session.apply_answer(self.state, session.next_item(self.state), False)
        self.assertEqual(self.state["streak"], 0)
        self.assertEqual(self.state["best"], 3)

    def test_the_session_finishes(self):
        self._answer_all_correct(20)
        self.assertTrue(session.finished(self.state))
        self.assertEqual(session.progress(self.state)["percent"], 100)
        self.assertIsNone(session.next_item(self.state))

    def test_progress_moves_before_anything_is_mastered(self):
        position = session.next_item(self.state)
        session.apply_answer(self.state, position, True)
        state = session.progress(self.state)
        self.assertEqual(state["mastered"], 0)
        self.assertGreater(state["percent"], 0)

    def test_rounds_prefer_the_weakest_terms(self):
        # Push one term to the top level, then check it is not in the batch
        # while ten fresh ones are waiting.
        self.state["levels"][9] = session.LEVELS - 1
        session.start_round(self.state)
        self.assertNotIn(9, self.state["queue"])


class PruneTests(unittest.TestCase):
    def test_a_deleted_card_drops_out_and_levels_survive(self):
        state = session.start_learn([1, 2, 3, 4], seed=1)
        state["levels"] = [0, 2, 1, 3]
        session.start_round(state)
        session.prune(state, [1, 3, 4])
        self.assertEqual(state["items"], [1, 3, 4])
        self.assertEqual(state["levels"], [0, 1, 3])
        self.assertTrue(all(0 <= p < 3 for p in state["queue"]))

    def test_pruning_everything_is_survivable(self):
        state = session.start_learn([1, 2], seed=1)
        session.start_round(state)
        session.prune(state, [])
        self.assertEqual(state["items"], [])
        self.assertEqual(state["queue"], [])
        self.assertFalse(session.finished(state))


class TestModeTests(unittest.TestCase):
    def setUp(self):
        self.terms = [f"term{n}" for n in range(30)]
        self.answers = [f"meaning{n}" for n in range(30)]

    def build(self, **kwargs):
        options = dict(wanted=10, types=("tf", "choice", "typed"),
                       direction="term", seed=42)
        options.update(kwargs)
        return session.build_test(self.terms, self.answers, **options)

    def test_length_and_no_repeats(self):
        questions = self.build()
        self.assertEqual(len(questions), 10)
        self.assertEqual(len({q["pos"] for q in questions}), 10)

    def test_it_replays_from_the_same_seed(self):
        self.assertEqual(self.build(), self.build())

    def test_a_different_seed_is_a_different_test(self):
        self.assertNotEqual(self.build(), self.build(seed=43))

    def test_types_are_spread_not_clustered(self):
        kinds = {q["type"] for q in self.build()}
        self.assertEqual(kinds, {"tf", "choice", "typed"})

    def test_true_false_is_balanced(self):
        tf = [q for q in self.build(types=("tf",), wanted=20)]
        truths = sum(1 for q in tf if q["truth"])
        self.assertEqual(truths, len(tf) // 2)

    def test_a_false_statement_shows_another_answer(self):
        for question in self.build(types=("tf",), wanted=20):
            if not question["truth"]:
                self.assertNotEqual(question["shown"], question["pos"])

    def test_choice_options_contain_the_answer(self):
        for question in self.build(types=("choice",)):
            self.assertIn(question["pos"], question["options"])

    def test_wanting_more_than_the_deck_has(self):
        questions = self.build(wanted=500)
        self.assertEqual(len(questions), 30)

    def test_scoring(self):
        questions = self.build()
        given = {str(i): {"correct": i % 2 == 0} for i in range(len(questions))}
        self.assertEqual(session.score(questions, given),
                         {"right": 5, "total": 10, "percent": 50})

    def test_scoring_an_empty_test_does_not_divide_by_zero(self):
        self.assertEqual(session.score([], {})["percent"], 0)


class PickTests(unittest.TestCase):
    def test_the_cap_comes_after_the_shuffle(self):
        # Taking the first N of deck order would give the same N every time.
        first = session.pick(1000, 20, grading.new_rng(1))
        second = session.pick(1000, 20, grading.new_rng(2))
        self.assertNotEqual(first, second)
        self.assertTrue(any(position > 20 for position in first))

    def test_zero_means_everything(self):
        self.assertEqual(len(session.pick(50, 0, grading.new_rng(1))), 50)

    def test_an_empty_deck(self):
        self.assertEqual(session.pick(0, 10, grading.new_rng(1)), [])


class MatchTests(unittest.TestCase):
    def test_pairs_are_capped_both_ways(self):
        self.assertEqual(len(session.match_pairs(100, 6, 1)), 6)
        self.assertEqual(len(session.match_pairs(4, 6, 1)), 4)
        self.assertEqual(len(session.match_pairs(100, 999, 1)),
                         session.MAX_MATCH_PAIRS)

    def test_pairs_are_distinct(self):
        pairs = session.match_pairs(100, 12, 3)
        self.assertEqual(len(set(pairs)), len(pairs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
