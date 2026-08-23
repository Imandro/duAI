import unittest


class TargetsTest(unittest.TestCase):
    def test_catalog_loads(self):
        from duai.core.targets import load_catalog

        catalog = load_catalog()
        self.assertIn("categories", catalog)
        self.assertIn("browsers", catalog)
        self.assertGreater(len(catalog["categories"]), 0)

    def test_build_targets_unique_ids(self):
        from duai.core.targets import build_targets

        targets = build_targets()
        ids = [t.id for t in targets]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(ids), 10)

    def test_exclusions_respected(self):
        from duai.core.targets import build_targets

        targets = build_targets(exclusions={"chatgpt_app"})
        self.assertNotIn("chatgpt_app", [t.id for t in targets])

    def test_rot13_marker_detection(self):
        from duai.core.registry_clean import _matches_ai, rot13

        encoded = rot13("chatgpt.exe")
        self.assertNotEqual(encoded.lower(), "chatgpt.exe")
        self.assertTrue(_matches_ai(rot13(encoded)))
        self.assertFalse(_matches_ai("notepad.exe"))

    def test_expand_paths(self):
        import os

        from duai.utils.paths import expand, iter_paths

        expanded = expand("%LOCALAPPDATA%/Temp")
        local = os.environ.get("LOCALAPPDATA", "")
        self.assertTrue(expanded.lower().startswith(local.lower()[:8]))
        results = iter_paths("%APPDATA%/Microsoft/Windows/Recent/*.lnk")
        self.assertIsInstance(results, list)

    def test_fmt_bytes(self):
        from duai.utils.paths import fmt_bytes

        self.assertEqual(fmt_bytes(0), "0 B")
        self.assertTrue("KB" in fmt_bytes(2048))


if __name__ == "__main__":
    unittest.main()
