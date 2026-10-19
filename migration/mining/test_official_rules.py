import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import official_rules as rules  # noqa: E402

PAGE = """<html><head><title>T</title><script>var x = "Channels must not be spam";</script>
<meta property="article:modified_time" content="2026-09-01"></head>
<body><nav>Help Center Community Sign in</nav><style>.a{color:red}</style>
<h2>Reused content</h2>
<p>Channels that   repeatedly
upload content&nbsp;without <b>significant</b> original commentary may not be monetized.</p>
<ul><li>First rule item here.</li><li>Second rule item here.</li></ul>
<p>Last updated: September 1, 2026</p></body></html>"""


class HtmlToText(unittest.TestCase):
    def test_drops_script_style_nav_head(self):
        text, meta = rules.html_to_text(PAGE)
        self.assertNotIn("var x", text)
        self.assertNotIn("color:red", text)
        self.assertNotIn("Sign in", text)
        self.assertNotIn("T\n", text + "\n")
        self.assertEqual(meta["article:modified_time"], "2026-09-01")

    def test_blocks_become_lines_and_inline_stays_inline(self):
        text, _ = rules.html_to_text(PAGE)
        lines = text.split("\n")
        self.assertIn("Reused content", lines)
        self.assertIn("Channels that repeatedly upload content without significant original commentary may not be monetized.",
                      lines)
        self.assertIn("First rule item here.", lines)
        self.assertIn("Second rule item here.", lines)

    def test_last_updated(self):
        text, meta = rules.html_to_text(PAGE)
        self.assertEqual(rules.last_updated(text, meta, {}), "Last updated: September 1, 2026")
        self.assertEqual(rules.last_updated("nothing", meta, {}), "article:modified_time: 2026-09-01")
        self.assertIsNone(rules.last_updated("nothing", {}, {}))


class Verbatim(unittest.TestCase):
    def setUp(self):
        self.text, _ = rules.html_to_text(PAGE)

    def test_exact_substring_kept_with_whitespace_normalised(self):
        kept, dropped = rules.verify([{"section": "Reused  content", "quote": "upload content without significant\n original commentary"}],
                                     self.text)
        self.assertEqual(dropped, 0)
        self.assertEqual(kept, [{"section": "Reused content", "quote": "upload content without significant original commentary"}])

    def test_quote_spanning_list_items_is_whitespace_only(self):
        kept, dropped = rules.verify([{"section": "", "quote": "First rule item here. Second rule item here."}], self.text)
        self.assertEqual((len(kept), dropped), (1, 0))
        self.assertEqual(kept[0]["section"], "(no heading)")

    def test_paraphrase_and_changed_words_dropped(self):
        quotes = [{"section": "x", "quote": "Channels that often upload content without original commentary may not be monetized."},
                  {"section": "x", "quote": "Channels that repeatedly upload content without significant original commentary will not be monetized."},
                  {"section": "x", "quote": "channels that repeatedly upload content"},  # case differs
                  {"section": "x", "quote": "Channels must not be spam"},  # only inside a script
                  {"section": "x", "quote": "Sign in"}]
        kept, dropped = rules.verify(quotes, self.text)
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 5)

    def test_short_fragments_dropped_and_duplicates_collapsed(self):
        q = "Channels that repeatedly upload content"
        kept, dropped = rules.verify([{"section": "a", "quote": "monetized"}, {"section": "a", "quote": q},
                                      {"section": "a", "quote": q + " "}], self.text)
        self.assertEqual(dropped, 1)
        self.assertEqual([k["quote"] for k in kept], [q])

    def test_topics_are_official_and_complete(self):
        self.assertEqual(len(rules.TOPICS), 13)
        for urls in rules.TOPICS.values():
            for u in urls:
                self.assertTrue(any(h in u for h in rules.OFFICIAL_HOSTS), u)

    def test_hl_en(self):
        self.assertEqual(rules.with_hl("https://support.google.com/youtube/answer/72431"),
                         "https://support.google.com/youtube/answer/72431?hl=en")


if __name__ == "__main__":
    unittest.main()
