"""M1 unit tests: SendInput struct layout, hotkey parsing, bar placement."""
import ctypes
import unittest

from app import win32
from app.hotkey import format_hotkey, parse_hotkey, vk_name
from app.names import app_label, render
from app.popup import display_text, mix, place


class TestWin32Structs(unittest.TestCase):
    def test_input_size(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(win32.INPUT), expected)

    def test_monitorinfo_size(self):
        self.assertEqual(ctypes.sizeof(win32.MONITORINFO), 40)


class TestParseHotkey(unittest.TestCase):
    def test_default(self):
        self.assertEqual(parse_hotkey("Ctrl+Shift+Space"),
                         (win32.MOD_CONTROL | win32.MOD_SHIFT, win32.VK_SPACE))

    def test_letter_and_fkey(self):
        self.assertEqual(parse_hotkey("alt+q"), (win32.MOD_ALT, ord("Q")))
        self.assertEqual(parse_hotkey("Ctrl+F12"), (win32.MOD_CONTROL, 0x7B))

    def test_format_roundtrip(self):
        for text in ("Ctrl+Shift+Space", "Alt+Q", "Ctrl+Alt+F9", "Ctrl+1", "Ctrl+Shift+/"):
            self.assertEqual(format_hotkey(*parse_hotkey(text)), text)

    def test_vk_name(self):
        self.assertEqual(vk_name(0x41), "A")
        self.assertEqual(vk_name(0x70), "F1")
        self.assertIsNone(vk_name(0x10))  # Shift alone is not a key

    def test_invalid(self):
        for bad in ("Space", "Shift+Space", "Ctrl+", "Ctrl+Nope", "Hyper+A", ""):
            with self.assertRaises(ValueError, msg=bad):
                parse_hotkey(bad)


class TestPlace(unittest.TestCase):
    AREA = (0, 0, 1920, 1040)

    def test_below_right(self):
        self.assertEqual(place(100, 100, 300, 200, self.AREA), (112, 112))

    def test_flips_near_bottom_right(self):
        self.assertEqual(place(1900, 1030, 300, 200, self.AREA), (1588, 818))

    def test_clamped_on_second_monitor_with_negative_coords(self):
        area = (-1280, 0, 0, 984)
        x, y = place(-1275, 5, 300, 200, area)
        self.assertGreaterEqual(x, -1280)
        self.assertLessEqual(x + 300, 0)
        self.assertGreaterEqual(y, 0)

    def test_bigger_than_area(self):
        self.assertEqual(place(50, 50, 3000, 2000, self.AREA), (0, 0))


class TestText(unittest.TestCase):
    def test_render(self):
        self.assertEqual(render("Hi {name}", "there"), "Hi there")

    def test_app_label(self):
        self.assertEqual(app_label("slack.exe"), "Slack")
        self.assertEqual(app_label("Discord.exe"), "Discord")
        self.assertEqual(app_label("foo.exe"), "Foo")
        self.assertEqual(app_label(""), "")

    def test_mix(self):
        self.assertEqual(mix("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(mix("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(mix("#000000", "#ff0000", 0.5), "#800000")

    def test_display_truncates(self):
        self.assertEqual(display_text("a\nb"), "a b")
        self.assertTrue(display_text("x" * 100).endswith("…"))
        self.assertLessEqual(len(display_text("x" * 100)), 48)


if __name__ == "__main__":
    unittest.main()
