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

    def test_modes_are_pure_inverses(self):
        light = PALETTES["claro"]
        dark = PALETTES["oscuro"]
        self.assertEqual((light["BG"], light["FG"]), ("#FFFFFF", "#000000"))
        self.assertEqual((dark["BG"], dark["FG"]), ("#000000", "#FFFFFF"))

    def test_palettes_share_keys(self):
        self.assertEqual(set(PALETTES["claro"].keys()), set(PALETTES["oscuro"].keys()))


if __name__ == "__main__":
    unittest.main()
