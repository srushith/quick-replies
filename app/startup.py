"""Start with Windows.

Unpackaged (plain exe / source): HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run,
value QuickReplies.

Packaged (Microsoft Store MSIX): the Run key doesn't work for packaged apps. The
manifest declares a startup task (TaskId below, disabled by default) and the user
switches it on in Settings > Apps > Startup. We open that page and read the task's
state for the checkmark.
"""
import os
import sys
import winreg

from app import win32
from app.log import debug

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "QuickReplies"
TASK_ID = "QuickRepliesStartup"  # must match AppxManifest.xml
_TASK_STATE_KEY = (r"Software\Classes\Local Settings\Software\Microsoft\Windows"
                   r"\CurrentVersion\AppModel\SystemAppData\{pfn}\{task}")
_ENABLED_STATES = {2, 4}  # Enabled, EnabledByPolicy

_pfn = win32.package_family_name()
packaged = _pfn is not None


def command():
    """What Windows should run at sign-in (unpackaged only)."""
    if getattr(sys, "frozen", False):  # PyInstaller exe
        return f'"{sys.executable}"'
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw
    return f'"{exe}" "{os.path.join(root, "QuickReplies.pyw")}"'


def current():
    """The registered Run command, or None."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, VALUE)
            return value
    except OSError:
        return None


def _task_enabled():
    try:
        key = _TASK_STATE_KEY.format(pfn=_pfn, task=TASK_ID)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            state, _ = winreg.QueryValueEx(k, "State")
            return state in _ENABLED_STATES
    except OSError:
        return False  # never toggled yet = disabled (manifest default)


def is_enabled():
    return _task_enabled() if packaged else current() is not None


def open_startup_settings():
    try:
        os.startfile("ms-settings:startupapps")
        return True
    except OSError as e:
        debug(f"could not open startup settings: {e}")
        return False


def set_enabled(on):
    """Add or remove the Run value. Returns True on success; never raises.

    Packaged: we can't change it ourselves; open Windows' Startup apps page instead.
    """
    if packaged:
        return open_startup_settings()
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
    (e.g. the exe was moved). Returns the effective state. Packaged: Windows owns it."""
    if packaged:
        return _task_enabled()
    cur = current()
    if want and cur != command():
        set_enabled(True)
    elif not want and cur is not None:
        set_enabled(False)
    return is_enabled()
