import unittest


class ParseCommandTest(unittest.TestCase):
    def test_simple(self):
        from duai.ui.console_view import parse_command

        cmd, args, flags = parse_command("estado")
        self.assertEqual(cmd, "estado")
        self.assertEqual(args, [])
        self.assertEqual(flags, {})

    def test_args_and_flags(self):
        from duai.ui.console_view import parse_command

        cmd, args, flags = parse_command("limpiar todo --modo=cuarentena --confirmar")
        self.assertEqual(cmd, "limpiar")
        self.assertIn("todo", args)
        self.assertEqual(flags.get("modo"), "cuarentena")
        self.assertTrue(flags.get("confirmar"))

    def test_alias_normalization(self):
        from duai.ui.console_view import parse_command

        for alias, expected in (("help", "ayuda"), ("scan", "escanear"), ("cls", "limpiarpantalla")):
            cmd, _, _ = parse_command(alias)
            self.assertEqual(cmd, expected)

    def test_case_insensitive_and_empty(self):
        from duai.ui.console_view import parse_command

        self.assertIsNone(parse_command("   ")[0])
        cmd, _, _ = parse_command("PANICO")
        self.assertEqual(cmd, "panico")

    def test_category_keys_cover_main_groups(self):
        from duai.ui.console_view import CATEGORY_KEYS

        self.assertEqual(CATEGORY_KEYS["apps"], "Aplicaciones de IA")
        self.assertEqual(CATEGORY_KEYS["navegador"], "Navegador")
        self.assertEqual(CATEGORY_KEYS["sistema"], "Sistema")


if __name__ == "__main__":
    unittest.main()
