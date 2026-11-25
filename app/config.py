"""Settings: %APPDATA%\\QuickRepliesDesktop\\settings.json.

Atomic writes (temp file + os.replace). A corrupt file is moved to settings.bad.json
and the app starts from defaults. Never raises on bad config. Never logs reply text.
"""
import copy
import json
import os
import tempfile

from app.log import debug

VERSION = 1

DEFAULTS = {
    "version": VERSION,
    "replies": ["Hi {name}", "Following up on the above", "Understood", "Thanks"],
    "hotkey": "Ctrl+Shift+Space",
    "press_enter": False,
    "keep_open": False,          # "pin": bar stays open after inserting
    "start_with_windows": False,
}


def asset_path(name):
    """Path to a bundled asset, both from source and inside the PyInstaller exe."""
    import sys
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


def default_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "QuickRepliesDesktop", "settings.json")


def defaults():
    return copy.deepcopy(DEFAULTS)


def _valid_hotkey(text):
    from app.hotkey import parse_hotkey  # local import: keeps config importable on its own
    try:
        parse_hotkey(text)
        return True
    except ValueError:
        return False


def normalize(data):
    """Return a clean settings dict from whatever was loaded; unknown keys dropped."""
    cfg = defaults()
    if not isinstance(data, dict):
        return cfg
    replies = data.get("replies")
    if isinstance(replies, list):
        cfg["replies"] = [r for r in replies if isinstance(r, str) and r.strip()]
    hk = data.get("hotkey")
    if isinstance(hk, str) and _valid_hotkey(hk):
        cfg["hotkey"] = hk
    for key in ("press_enter", "keep_open", "start_with_windows"):
        if isinstance(data.get(key), bool):
            cfg[key] = data[key]
    cfg["version"] = VERSION  # future migrations go here, keyed on data.get("version")
    return cfg


def load(path=None):
    path = path or default_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("settings is not a JSON object")
    except FileNotFoundError:
        cfg = defaults()
        save(cfg, path)
        return cfg
    except (OSError, ValueError) as e:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        debug(f"settings unreadable ({type(e).__name__}); backing up and using defaults")
        _backup_bad(path)
        cfg = defaults()
        save(cfg, path)
        return cfg
    return normalize(data)


def _backup_bad(path):
    try:
        os.replace(path, os.path.join(os.path.dirname(path), "settings.bad.json"))
    except OSError as e:
        debug(f"could not back up bad settings: {e}")


def save(cfg, path=None):
    """Atomically write settings. Returns True on success; never raises."""
    path = path or default_path()
    tmp = None
    try:
        folder = os.path.dirname(path)
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="settings.", suffix=".tmp", dir=folder)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(normalize(cfg), f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except OSError as e:
        debug(f"could not save settings: {e}")
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False
