"""Start with Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run, value QuickReplies."""
import os
import sys
import winreg

from app.log import debug

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "QuickReplies"


def command():
    """What Windows should run at sign-in."""
    if getattr(sys, "frozen", False):  # PyInstaller exe
        return f'"{sys.executable}"'
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw
    return f'"{exe}" "{os.path.join(root, "QuickReplies.pyw")}"'


def current():
    """The registered command, or None."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, VALUE)
            return value
    except OSError:
        return None


def is_enabled():
    return current() is not None


def set_enabled(on):
    """Add or remove the Run value. Returns True on success; never raises."""
    try:
        if on:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                    winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, command())
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.DeleteValue(k, VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        debug(f"could not update Run key: {e}")
        return False


def sync(want):
    """At startup: make the registry match the setting, and fix a stale path
    (e.g. the exe was moved). Returns the effective state."""
    cur = current()
    if want and cur != command():
        set_enabled(True)
    elif not want and cur is not None:
        set_enabled(False)
    return is_enabled()
