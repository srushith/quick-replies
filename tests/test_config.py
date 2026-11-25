import json
import os
import shutil
import tempfile
import unittest

from app import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "settings.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, text):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_missing_file_creates_defaults(self):
        cfg = config.load(self.path)
        self.assertEqual(cfg, config.DEFAULTS)
        self.assertTrue(os.path.exists(self.path))

    def test_defaults_unchanged(self):
        self.assertEqual(config.DEFAULTS["replies"],
                         ["Hi {name}", "Following up on the above", "Understood", "Thanks"])
        self.assertEqual(config.DEFAULTS["hotkey"], "Ctrl+Shift+Space")
        self.assertFalse(config.DEFAULTS["press_enter"])

    def test_roundtrip(self):
        cfg = config.defaults()
        cfg["replies"] = ["Hallo {name} 👋", "Ünïcode"]
        cfg["hotkey"] = "Ctrl+Alt+R"
        cfg["press_enter"] = True
        self.assertTrue(config.save(cfg, self.path))
        self.assertEqual(config.load(self.path), cfg)

    def test_no_temp_files_left(self):
        config.save(config.defaults(), self.path)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["settings.json"])

    def test_corrupt_file_backed_up(self):
        self.write("{not json")
        cfg = config.load(self.path)
        self.assertEqual(cfg, config.DEFAULTS)
        bad = os.path.join(os.path.dirname(self.path), "settings.bad.json")
        with open(bad, encoding="utf-8") as f:
            self.assertEqual(f.read(), "{not json")
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), config.DEFAULTS)

    def test_not_an_object(self):
        self.write("[1, 2]")
        self.assertEqual(config.load(self.path), config.DEFAULTS)

    def test_bad_values_fall_back_per_key(self):
        self.write(json.dumps({"replies": ["ok", 5, "", "  "], "hotkey": "Shift+Q",
                               "press_enter": "yes", "start_with_windows": True,
                               "extra": 1}))
        cfg = config.load(self.path)
        self.assertEqual(cfg["replies"], ["ok"])
        self.assertEqual(cfg["hotkey"], "Ctrl+Shift+Space")
        self.assertFalse(cfg["press_enter"])
        self.assertTrue(cfg["start_with_windows"])
        self.assertNotIn("extra", cfg)

    def test_keep_open(self):
        self.assertFalse(config.DEFAULTS["keep_open"])
        self.write(json.dumps({"keep_open": True}))
        self.assertTrue(config.load(self.path)["keep_open"])
        self.write(json.dumps({"keep_open": "yes"}))
        self.assertFalse(config.load(self.path)["keep_open"])

    def test_empty_reply_list_is_kept(self):
        self.write(json.dumps({"replies": []}))
        self.assertEqual(config.load(self.path)["replies"], [])

    def test_save_failure_does_not_raise(self):
        blocker = os.path.join(self.dir, "file")
        open(blocker, "w").close()
        self.assertFalse(config.save(config.defaults(), os.path.join(blocker, "settings.json")))


if __name__ == "__main__":
    unittest.main()
