import unittest


class SilentCommandTest(unittest.TestCase):
    def test_msiexec_adds_quiet(self):
        from duai.core.uninstaller import build_silent_command

        entry = {"quiet_string": "", "uninstall_string": "msiexec /x {GUID}"}
        cmd = build_silent_command(entry)
        self.assertIn("/quiet", cmd)
        self.assertIn("/norestart", cmd)

    def test_squirrel_update_exe(self):
        from duai.core.uninstaller import build_silent_command

        entry = {
            "quiet_string": "",
            "uninstall_string": r'"C:\Users\x\AppData\Local\ChatGPT\Update.exe" --uninstall',
        }
        cmd = build_silent_command(entry)
        self.assertIn("-s", cmd)

        entry2 = {
            "quiet_string": r'"C:\x\Update.exe"',
            "uninstall_string": r'"C:\x\Update.exe"',
        }
        cmd2 = build_silent_command(entry2)
        self.assertIn("--uninstall", cmd2)
        self.assertTrue(cmd2.endswith("-s"))

    def test_inno_nsis_flags(self):
        from duai.core.uninstaller import build_silent_command

        entry = {"quiet_string": "", "uninstall_string": r'"C:\App\unins000.exe"'}
        cmd = build_silent_command(entry)
        self.assertIn("/VERYSILENT", cmd)
        self.assertIn("/NORESTART", cmd)

        entry_nsis = {"quiet_string": "", "uninstall_string": r"C:\App\uninstall.exe"}
        cmd_nsis = build_silent_command(entry_nsis)
        self.assertIn("/S", cmd_nsis)

    def test_quiet_preferred_and_already_silent(self):
        from duai.core.uninstaller import build_silent_command

        entry = {
            "quiet_string": r'"C:\x\un.exe" /S',
            "uninstall_string": r'"C:\x\un.exe"',
        }
        cmd = build_silent_command(entry)
        self.assertEqual(cmd, r'"C:\x\un.exe" /S')

    def test_empty_returns_none(self):
        from duai.core.uninstaller import build_silent_command

        self.assertIsNone(build_silent_command({"quiet_string": "", "uninstall_string": ""}))


class AiAppNameTest(unittest.TestCase):
    def test_matches(self):
        from duai.core.uninstaller import is_ai_app_name

        self.assertTrue(is_ai_app_name("ChatGPT"))
        self.assertTrue(is_ai_app_name("Cursor Editor"))
        self.assertFalse(is_ai_app_name("Mozilla Firefox"))
        self.assertFalse(is_ai_app_name("Notepad++"))


if __name__ == "__main__":
    unittest.main()
