import unittest

from duai.ui.theme import PALETTES, render_css

TOKENS = ["BG", "FG", "SOFT", "BODY", "LINE", "GRID", "ALT", "HOVER", "HANDLE"]


class ThemeTest(unittest.TestCase):
    def test_all_tokens_replaced_for_every_mode(self):
        for mode in PALETTES:
            css = render_css(mode)
            for token in TOKENS:
                self.assertNotIn("__" + token + "__", css, f"token sin sustituir en {mode}")
            self.assertNotIn("__", css)

    def test_dark_mode_colors(self):
        dark = PALETTES["oscuro"]
        self.assertEqual((dark["BG"], dark["FG"]), ("#000000", "#FFFFFF"))

    def test_palette_has_all_keys(self):
        expected = {"BG", "FG", "SOFT", "BODY", "LINE", "GRID", "ALT", "HOVER", "HANDLE"}
        self.assertEqual(set(PALETTES["oscuro"].keys()), expected)


if __name__ == "__main__":
    unittest.main()
