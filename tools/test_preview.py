#!/usr/bin/env python3
"""Cards preview tests — run from the add-on root:

    python3 tools/test_preview.py

`features/preview/{content,grid}` never import `aqt`, so they load directly
under a synthetic package name. Keep it that way; `screens/preview.py` is where
anything needing Anki belongs.
"""

import importlib.util
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = "awd_preview"

_package = types.ModuleType(PACKAGE)
_package.__path__ = [str(ROOT / "features" / "preview")]
sys.modules[PACKAGE] = _package


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / "features" / "preview" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PACKAGE}.{name}"] = module
    spec.loader.exec_module(module)
    return module


content = _load("content")
grid = _load("grid")


class PlaceholderTests(unittest.TestCase):
    """The four things the backend leaves for Anki's front-end to finish.

    Every one of them renders as literal text if it survives, which reads as a
    broken card rather than as a missing feature.
    """

    def test_play_becomes_a_button_for_the_matching_file(self):
        out = content.clean("hi [anki:play:q:0]", ["boo.mp3"])
        self.assertIn("awd:playfile:boo.mp3", out)
        self.assertNotIn("anki:play", out)

    def test_play_indexes_into_its_own_side(self):
        out = content.clean("[anki:play:a:1]", ["first.mp3", "second.mp3"])
        self.assertIn("second.mp3", out)
        self.assertNotIn("first.mp3", out)

    def test_a_tts_tag_has_no_file_so_it_leaves_no_button(self):
        out = content.clean("word [anki:play:q:0]", [None])
        self.assertNotIn("awd-skin-audio", out)
        self.assertNotIn("anki:play", out)

    def test_an_index_with_no_tag_behind_it_is_dropped(self):
        self.assertEqual(content.clean("[anki:play:q:7]", ["only.mp3"]), "")

    def test_a_filename_with_quotes_cannot_break_out_of_the_pycmd(self):
        out = content.clean("[anki:play:q:0]", ["a'b\".mp3"])
        self.assertNotIn("a'b\".mp3", out)
        self.assertIn("&#x27;", out)

    def test_every_type_placeholder_goes(self):
        for raw in ("[[type:Front]]", "[[type:nc:Front]]", "[[type:cloze:Text]]"):
            self.assertEqual(content.clean(f"a{raw}b"), "ab")

    def test_a_tts_wrapper_keeps_the_words_inside_it(self):
        out = content.clean('[anki:tts lang=en_US voices=x]hello[/anki:tts]')
        self.assertEqual(out, "hello")


class StrippingTests(unittest.TestCase):
    def test_template_script_and_style_go(self):
        out = content.clean("<style>.card{color:red}</style>"
                            "<script>alert(1)</script>keep")
        self.assertEqual(out, "keep")

    def test_inline_handlers_go_but_the_element_stays(self):
        out = content.clean('<div onclick="steal()" class="x">word</div>')
        self.assertNotIn("onclick", out)
        self.assertIn('class="x"', out)
        self.assertIn("word", out)

    def test_a_handler_written_without_quotes_still_goes(self):
        self.assertNotIn("onerror", content.clean("<img src=x onerror=boom()>"))

    def test_inline_style_survives_because_it_is_how_notes_are_styled(self):
        out = content.clean("<div style='color:#c33;text-align:left'>word</div>")
        self.assertIn("color:#c33", out)
        self.assertIn("text-align:left", out)

    def test_an_absolute_font_size_becomes_relative_to_the_tile(self):
        # A vocabulary deck writes 100px for the word; in a 270px tile that is
        # one and a half characters. Anki's own card default is 20px.
        self.assertIn("font-size:5em",
                      content.clean("<div style='font-size: 100px;'>x</div>"))
        self.assertIn("font-size:0.6em",
                      content.clean("<i style='font-size:12px'>y</i>"))

    def test_a_relative_font_size_is_already_fine(self):
        self.assertIn("font-size:150%",
                      content.clean("<u style='font-size:150%'>w</u>"))

    def test_the_hierarchy_between_two_sizes_survives(self):
        out = content.clean("<div style='font-size:100px'>a</div>"
                            "<div style='font-size:20px'>b</div>")
        self.assertIn("font-size:5em", out)
        self.assertIn("font-size:1em", out)

    def test_an_occlusion_canvas_goes_and_leaves_the_picture(self):
        out = content.clean('<div id="image-occlusion-container">'
                            '<img id="image" src="pic.jpg">'
                            '<canvas id="canvas"></canvas></div>')
        self.assertNotIn("canvas", out)
        self.assertIn("pic.jpg", out)


class CapTests(unittest.TestCase):
    def test_ordinary_markup_is_left_exactly_as_it_was(self):
        markup = "<div><b>word</b></div>"
        self.assertIs(content.cap(markup), markup)

    def test_an_enormous_face_falls_back_to_its_words(self):
        out = content.cap("<div>" + ("word " * 4000) + "</div>")
        self.assertLessEqual(len(out), content.MAX_FACE + 1)
        self.assertNotIn("<div>", out)
        self.assertTrue(out.endswith("\u2026"))


class BackSideTests(unittest.TestCase):
    """A tile that repeats its own question on the back wastes half of itself."""

    def test_the_answer_rule_splits_the_sides(self):
        self.assertEqual(
            content.back_only("Q", "Q<hr id=answer>A"), "A")

    def test_the_rule_is_matched_however_the_template_spells_it(self):
        for rule in ('<hr id=answer>', '<hr id="answer">', "<hr  id='answer' />"):
            self.assertEqual(content.back_only("Q", f"Q{rule}A"), "A")

    def test_a_template_without_the_rule_falls_back_to_the_prefix(self):
        self.assertEqual(content.back_only("Q", "QA"), "A")

    def test_a_back_that_shares_no_prefix_is_left_alone(self):
        self.assertEqual(content.back_only("Q", "answer only"), "answer only")

    def test_a_cloze_back_is_not_mistaken_for_a_repeat(self):
        # Both sides render the same field, so the answer neither carries the
        # rule nor starts with the question — it must survive whole.
        question = "The capital is [...]"
        answer = "The capital is <b>Paris</b>"
        self.assertEqual(content.back_only(question, answer), answer)


class BlankSideTests(unittest.TestCase):
    def test_markup_with_no_words_is_blank(self):
        self.assertTrue(content.is_blank("<div><br></div>  &nbsp; "))

    def test_an_image_only_side_is_not_blank(self):
        self.assertFalse(content.is_blank('<div><img src="a.jpg"></div>'))

    def test_words_are_not_blank(self):
        self.assertFalse(content.is_blank("<div>word</div>"))


class OptionTests(unittest.TestCase):
    def test_junk_falls_back_to_the_defaults(self):
        self.assertEqual(grid.clamp({"columns": 99, "ratio": "banana",
                                     "font": "big", "sort": None}),
                         dict(grid.DEFAULTS))

    def test_nothing_at_all_is_the_defaults(self):
        self.assertEqual(grid.clamp(None), dict(grid.DEFAULTS))

    def test_the_font_scale_is_clamped_rather_than_rejected(self):
        self.assertEqual(grid.clamp({"font": 5000})["font"], grid.FONT_MAX)
        self.assertEqual(grid.clamp({"font": 1})["font"], grid.FONT_MIN)

    def test_aspect_is_written_the_way_css_wants_it(self):
        self.assertEqual(grid.aspect("16:9"), "16 / 9")
        self.assertEqual(grid.aspect("nonsense"), "1 / 1")


class PagingTests(unittest.TestCase):
    def test_page_size_is_the_two_controls_multiplied(self):
        self.assertEqual(grid.per_page({"columns": 5, "rows": 4}), 20)

    def test_an_empty_deck_still_has_one_page(self):
        self.assertEqual(grid.page_count(0, 12), 1)
        self.assertEqual(grid.slice_page([], 3, 12), [])

    def test_a_partial_last_page_counts(self):
        self.assertEqual(grid.page_count(13, 12), 2)

    def test_a_page_past_the_end_lands_on_the_last_one(self):
        self.assertEqual(grid.clamp_page(99, 3), 2)
        self.assertEqual(grid.clamp_page(-4, 3), 0)

    def test_slicing_uses_the_clamped_page(self):
        items = list(range(25))
        self.assertEqual(grid.slice_page(items, 99, 10), [20, 21, 22, 23, 24])

    def test_resizing_keeps_the_first_visible_card_visible(self):
        # Page 3 of twelve starts at card 36; at eight per page that card is on
        # page 4, and the reader stays where they were rather than jumping.
        self.assertEqual(grid.page_for_index(3 * 12, 8), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
