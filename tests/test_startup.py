"""startup.py against a scratch registry key (never the real Run key)."""
import unittest
import winreg
from unittest import mock

from app import startup

TEST_KEY = r"Software\QuickRepliesDesktopTest\Run"


class TestStartup(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch.object(startup, "RUN_KEY", TEST_KEY)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        for key in (TEST_KEY, r"Software\QuickRepliesDesktopTest"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except OSError:
                pass

    def test_enable_disable(self):
        self.assertFalse(startup.is_enabled())
        self.assertTrue(startup.set_enabled(True))
        self.assertEqual(startup.current(), startup.command())
        self.assertTrue(startup.set_enabled(False))
        self.assertFalse(startup.is_enabled())
        self.assertTrue(startup.set_enabled(False))  # removing twice is fine

    def test_sync_fixes_stale_path(self):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, TEST_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, startup.VALUE, 0, winreg.REG_SZ, r'"C:\old\QuickReplies.exe"')
        self.assertTrue(startup.sync(True))
        self.assertEqual(startup.current(), startup.command())
        self.assertFalse(startup.sync(False))

    def test_command_from_source_uses_launcher(self):
        cmd = startup.command()
        self.assertIn("QuickReplies.pyw", cmd)
        self.assertTrue(cmd.startswith('"'))


if __name__ == "__main__":
    unittest.main()
