"""Global hotkey: RegisterHotKey on a dedicated thread that pumps its own messages.

The thread never touches Tk; it puts "hotkey" on a queue that Tk polls.
"""
import ctypes
import threading
from ctypes import wintypes

from app import win32
from app.log import debug

HOTKEY_ID = 1

_MODS = {
    "ctrl": win32.MOD_CONTROL, "control": win32.MOD_CONTROL,
    "alt": win32.MOD_ALT,
    "shift": win32.MOD_SHIFT,
    "win": win32.MOD_WIN,
}

_NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}


def parse_hotkey(text):
    """'Ctrl+Shift+Space' -> (modifiers, vk). Raises ValueError if invalid."""
    parts = [p.strip() for p in text.split("+")]
    if len(parts) < 2 or any(not p for p in parts):
        raise ValueError(f"invalid hotkey: {text!r}")
    mods = 0
    for p in parts[:-1]:
        m = _MODS.get(p.lower())
        if m is None:
            raise ValueError(f"unknown modifier: {p!r}")
        mods |= m
    key = parts[-1].lower()
    if key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif len(key) == 1 and (key.isascii() and key.isalnum()):
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"unknown key: {parts[-1]!r}")
    if not mods & (win32.MOD_CONTROL | win32.MOD_ALT):
        raise ValueError("hotkey must include Ctrl or Alt")
    return mods, vk


_VK_NAMES = {
    0x20: "Space", 0x0D: "Enter", 0x09: "Tab", 0x08: "Backspace", 0x2D: "Insert",
    0x2E: "Delete", 0x24: "Home", 0x23: "End", 0x21: "PageUp", 0x22: "PageDown",
    0x26: "Up", 0x28: "Down", 0x25: "Left", 0x27: "Right",
    0xC0: "`", 0xBD: "-", 0xBB: "=", 0xDB: "[", 0xDD: "]", 0xDC: "\\",
    0xBA: ";", 0xDE: "'", 0xBC: ",", 0xBE: ".", 0xBF: "/",
}


def vk_name(vk):
    """Windows VK code -> key name used in hotkey strings, or None if unsupported."""
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return _VK_NAMES.get(vk)


def format_hotkey(mods, vk):
    """(modifiers, vk) -> 'Ctrl+Shift+Space'. Raises ValueError if vk is unsupported."""
    name = vk_name(vk)
    if name is None:
        raise ValueError(f"unsupported key code {vk:#x}")
    parts = [label for bit, label in ((win32.MOD_CONTROL, "Ctrl"), (win32.MOD_ALT, "Alt"),
                                      (win32.MOD_SHIFT, "Shift"), (win32.MOD_WIN, "Win"))
             if mods & bit]
    return "+".join(parts + [name])


class HotkeyListener:
    """Registers one global hotkey on its own thread. on_fire is called on that thread."""

    def __init__(self, hotkey_text, on_fire):
        self.mods, self.vk = parse_hotkey(hotkey_text)
        self.on_fire = on_fire
        self._thread = None
        self._tid = 0
        self._ready = threading.Event()
        self.ok = False
        self.error = 0

    def start(self, timeout=2.0):
        """Start and wait for registration. Returns True if the hotkey was registered."""
        self._thread = threading.Thread(target=self._run, name="hotkey", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.ok

    def stop(self):
        if self._thread and self._thread.is_alive() and self._tid:
            win32.PostThreadMessageW(self._tid, win32.WM_QUIT, 0, 0)
            self._thread.join(1.0)
        self._thread = None

    def _run(self):
        self._tid = win32.GetCurrentThreadId()
        msg = wintypes.MSG()
        # Make sure this thread has a message queue before anyone posts to it.
        win32.PeekMessageW(ctypes.byref(msg), None, 0, 0, win32.PM_NOREMOVE)
        self.ok = bool(win32.RegisterHotKey(None, HOTKEY_ID,
                                            self.mods | win32.MOD_NOREPEAT, self.vk))
        if not self.ok:
            self.error = win32.get_last_error()
        self._ready.set()
        if not self.ok:
            debug(f"RegisterHotKey failed, error {self.error}")
            return
        try:
            while True:
                r = win32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r == 0 or r == -1:  # WM_QUIT or error
                    break
                if msg.message == win32.WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self.on_fire()
        finally:
            win32.UnregisterHotKey(None, HOTKEY_ID)
