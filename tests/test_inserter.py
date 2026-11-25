"""Key sequence sent by the inserter (Win32 calls and the clock are faked; no real input)."""
import unittest
from unittest import mock

from app import inserter, win32

PASTE = [(win32.VK_CONTROL, False), (win32.VK_V, False), (win32.VK_V, True),
         (win32.VK_CONTROL, True)]
ENTER = [(win32.VK_RETURN, False), (win32.VK_RETURN, True)]


class Fake:
    """Fake clock + keyboard: Shift is physically held until `release_at` seconds."""

    def __init__(self, release_at):
        self.now = 0.0
        self.release_at = release_at
        self.sent = []  # (time, events, shift_down_at_that_moment)

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.now += max(s, 0.001)

    def shift_down(self):
        return self.now < self.release_at

    def is_down(self, vk):
        self.now += 0.001  # each poll takes a moment
        return vk == win32.VK_SHIFT and self.shift_down()

    def send_keys(self, events):
        self.sent.append((self.now, list(events), self.shift_down()))
        return len(events)


class TestEnterAfterShift(unittest.TestCase):
    def run_insert(self, release_at, press_enter=True):
        f = Fake(release_at)
        with mock.patch.object(win32, "is_down", f.is_down), \
             mock.patch.object(win32, "send_keys", f.send_keys), \
             mock.patch.object(inserter, "_wait_foreground", return_value=True), \
             mock.patch.object(inserter, "_snapshot", return_value="XYZ"), \
             mock.patch.object(inserter, "_write_text", return_value=42), \
             mock.patch.object(win32, "GetClipboardSequenceNumber", return_value=42), \
             mock.patch.object(inserter.time, "monotonic", f.monotonic), \
             mock.patch.object(inserter.time, "sleep", f.sleep):
            ok = inserter._insert("Hi Priya", 1, press_enter, 0)
        return ok, f

    def test_shift_held_past_paste_then_released(self):
        # The reported bug: Shift still down after the 1 s pre-paste wait. The paste goes
        # ahead, but Enter must wait until Shift is up (else Shift+Enter = new line).
        ok, f = self.run_insert(release_at=2.5)
        self.assertTrue(ok)
        self.assertEqual([events for _, events, _ in f.sent], [PASTE, ENTER])
        enter_time, _, shift_at_enter = f.sent[1]
        self.assertFalse(shift_at_enter, "Enter was sent while Shift was held")
        self.assertGreaterEqual(enter_time, 2.5)

    def test_shift_never_released(self):
        # Held past the 5 s limit: insert the text but don't send (no stray new line).
        ok, f = self.run_insert(release_at=10**6)
        self.assertTrue(ok)
        self.assertEqual([events for _, events, _ in f.sent], [PASTE])

    def test_quick_release_sends_normally(self):
        ok, f = self.run_insert(release_at=0.2)
        self.assertEqual([events for _, events, _ in f.sent], [PASTE, ENTER])
        self.assertFalse(any(shift for _, _, shift in f.sent))

    def test_no_enter_when_not_sending(self):
        ok, f = self.run_insert(release_at=0.0, press_enter=False)
        self.assertEqual([events for _, events, _ in f.sent], [PASTE])


if __name__ == "__main__":
    unittest.main()
