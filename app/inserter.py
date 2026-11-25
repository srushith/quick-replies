"""Insert text at the caret of another app: focus it, paste via Ctrl+V, restore clipboard.

Never logs the reply text or clipboard contents.
"""
import ctypes
import threading
import time

from app import win32
from app.log import debug

_busy = threading.Lock()

_EXCLUDE_FORMATS = ("ExcludeClipboardContentFromMonitorProcessing",)
# Documented flag that keeps an item out of Win+V history and cloud clipboard (DWORD 0).
_ZERO_DWORD_FORMATS = ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")


# ---------------------------------------------------------------- clipboard
def _open_clipboard(owner_hwnd, tries=20):
    for _ in range(tries):
        if win32.OpenClipboard(owner_hwnd):
            return True
        time.sleep(0.02)
    return False


def _alloc(data: bytes):
    h = win32.GlobalAlloc(win32.GMEM_MOVEABLE, max(len(data), 1))
    if not h:
        return None
    p = win32.GlobalLock(h)
    if not p:
        win32.GlobalFree(h)
        return None
    ctypes.memmove(p, data, len(data))
    win32.GlobalUnlock(h)
    return h


def _set_data(fmt, data: bytes):
    h = _alloc(data)
    if h and not win32.SetClipboardData(fmt, h):
        win32.GlobalFree(h)  # ownership only passes to the system on success
        return False
    return bool(h)


def _read_text():
    """Current CF_UNICODETEXT (or None). Caller must have the clipboard open."""
    if not win32.IsClipboardFormatAvailable(win32.CF_UNICODETEXT):
        return None
    h = win32.GetClipboardData(win32.CF_UNICODETEXT)
    if not h:
        return None
    p = win32.GlobalLock(h)
    if not p:
        return None
    try:
        return ctypes.wstring_at(p)
    finally:
        win32.GlobalUnlock(h)


def _write_text(text, owner_hwnd, private=True):
    """Replace the clipboard with text (None = just empty it). Returns new sequence number or None."""
    if not _open_clipboard(owner_hwnd):
        return None
    try:
        win32.EmptyClipboard()
        if text is not None:
            if not _set_data(win32.CF_UNICODETEXT, (text + "\0").encode("utf-16-le")):
                return None
        if private:
            for name in _EXCLUDE_FORMATS:
                _set_data(win32.RegisterClipboardFormatW(name), b"\0")
            for name in _ZERO_DWORD_FORMATS:
                _set_data(win32.RegisterClipboardFormatW(name), b"\0\0\0\0")
    finally:
        win32.CloseClipboard()
    return win32.GetClipboardSequenceNumber()


def _snapshot(owner_hwnd):
    if not _open_clipboard(owner_hwnd):
        return None
    try:
        return _read_text()
    finally:
        win32.CloseClipboard()


# ---------------------------------------------------------------- keyboard
_MODIFIERS = (win32.VK_CONTROL, win32.VK_SHIFT, win32.VK_MENU, win32.VK_LWIN, win32.VK_RWIN)


def _wait_modifiers_released(timeout=1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not any(win32.is_down(vk) for vk in _MODIFIERS):
            return True
        time.sleep(0.01)
    return False


def _wait_foreground(target, timeout=0.5):
    end = time.monotonic() + timeout
    retried = False
    while time.monotonic() < end:
        if win32.GetForegroundWindow() == target:
            return True
        if not retried and time.monotonic() > end - timeout / 2:
            win32.force_foreground(target)
            retried = True
        time.sleep(0.01)
    return win32.GetForegroundWindow() == target


# ---------------------------------------------------------------- public
def insert(text, target, press_enter, owner_hwnd, on_done=None):
    """Insert text into the target window on a worker thread.

    The caller (Tk thread) should already have called win32.force_foreground(target)
    and hidden the bar. on_done(ok) is called on the worker thread.
    """
    if not _busy.acquire(blocking=False):
        debug("insert ignored: previous insert still running")
        return

    def work():
        ok = False
        try:
            ok = _insert(text, target, press_enter, owner_hwnd)
        except Exception as e:  # never crash the app on an insert
            debug(f"insert failed: {type(e).__name__}: {e}")
        finally:
            _busy.release()
            if on_done:
                on_done(ok)

    threading.Thread(target=work, name="insert", daemon=True).start()


def _insert(text, target, press_enter, owner_hwnd):
    if not _wait_foreground(target):
        debug("target window did not come to the foreground; not pasting")
        return False
    if not _wait_modifiers_released():
        debug("modifiers still held after 1s; pasting anyway")

    saved = _snapshot(owner_hwnd)
    our_seq = _write_text(text, owner_hwnd)
    if our_seq is None:
        debug("could not set clipboard")
        return False

    sent = win32.send_keys([(win32.VK_CONTROL, False), (win32.VK_V, False),
                            (win32.VK_V, True), (win32.VK_CONTROL, True)])
    if sent != 4:
        debug(f"SendInput sent {sent}/4 events, error {win32.get_last_error()}"
              " (target may be running as administrator)")
    if press_enter and sent == 4:
        time.sleep(0.06)
        win32.send_keys([(win32.VK_RETURN, False), (win32.VK_RETURN, True)])

    time.sleep(0.25)
    if win32.GetClipboardSequenceNumber() == our_seq:
        # Restore the user's text; if there was none (empty, image, files), clear ours.
        _write_text(saved, owner_hwnd)
    else:
        debug("clipboard changed during insert; not restoring")
    return sent == 4
