"""Quick Replies Desktop entry point.

    python -m app.main [--debug]
"""
import os
import queue
import signal
import sys
import tkinter as tk

from app import config, inserter, log, names, startup, win32
from app.hotkey import HotkeyListener
from app.log import debug
from app.popup import ReplyBar
from app.settings_window import SettingsWindow
from app.tray import Tray

MUTEX_NAME = "Local\\QuickRepliesDesktop"

# Windows that are never a useful insert target (taskbar, tray overflow, desktop).
_SHELL_CLASSES = {
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
    "TopLevelWindowForOverflowXamlIsland", "Progman", "WorkerW",
    "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow",
}


def set_dpi_awareness():
    try:
        if win32.SetProcessDpiAwarenessContext and win32.SetProcessDpiAwarenessContext(
                win32.DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return "per-monitor v2"
    except OSError:
        pass
    try:
        if win32.SetProcessDpiAwareness:
            win32.SetProcessDpiAwareness(win32.PROCESS_PER_MONITOR_DPI_AWARE)
            return "per-monitor"
    except OSError:
        pass
    win32.SetProcessDPIAware()
    return "system"


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = config.load()
        self.events = queue.Queue()
        self.target = None
        self.last_target = None   # last real app window, for "Open bar" from the tray
        self.rendered = []
        self.name = "there"
        self.context = ""
        self.hotkey = None
        self.hotkey_ok = False
        self.bar = ReplyBar(root, on_pick=self.pick, on_add=self.add_reply,
                            on_settings=self.open_settings, on_pin=self.toggle_pin)
        self.bar.set_pinned(self.cfg["keep_open"])
        self.settings = SettingsWindow(root, self)
        self.tray = Tray(self.events, lambda: startup.is_enabled() if startup.packaged
                         else self.cfg["start_with_windows"])
        self.cfg["start_with_windows"] = startup.sync(self.cfg["start_with_windows"])
        self.owner_hwnd = win32.root_hwnd(root.winfo_id())

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self.tray.start(self._tooltip())
        if self._register(self.cfg["hotkey"]):
            debug(f"hotkey {self.cfg['hotkey']} registered")
        else:
            debug(f"hotkey {self.cfg['hotkey']} unavailable")
            self.tray.notify(f"{self.cfg['hotkey']} is already used by another app. "
                             "Pick a different shortcut in Settings.")
            self.root.after(300, self.open_settings)
        self.root.after(30, self.poll)
        self.root.after(300, self.track_foreground)

    def quit(self):
        self.settings.close()
        if self.hotkey:
            self.hotkey.stop()
        self.tray.stop()
        self.root.destroy()

    def save(self):
        config.save(self.cfg)

    def _tooltip(self):
        return f"Quick Replies — {self.cfg['hotkey']}" if self.hotkey_ok else \
            "Quick Replies — shortcut unavailable"

    # ------------------------------------------------------------ hotkey
    def _register(self, text):
        listener = HotkeyListener(text, lambda: self.events.put("hotkey"))
        if listener.start():
            self.hotkey, self.hotkey_ok = listener, True
        else:
            self.hotkey, self.hotkey_ok = None, False
        self.tray.set_tooltip(self._tooltip())
        return self.hotkey_ok

    def suspend_hotkey(self):
        if self.hotkey:
            self.hotkey.stop()
            self.hotkey = None

    def resume_hotkey(self):
        if not self.hotkey:
            self._register(self.cfg["hotkey"])

    def set_hotkey(self, text):
        """Switch to a new hotkey live. Returns (ok, message for the user)."""
        self.suspend_hotkey()
        if self._register(text):
            self.cfg["hotkey"] = text
            self.save()
            self.tray.set_tooltip(self._tooltip())
            return True, f"Saved. Press {text} in any app."
        self._register(self.cfg["hotkey"])  # put the old one back
        return False, f"{text} is already used by another app. Try another."

    # ------------------------------------------------------------ events
    def poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev == "hotkey":
                    self.on_hotkey()
                elif ev == "open_bar":
                    self.open_bar_from_tray()
                elif ev == "settings":
                    self.open_settings()
                elif ev == "toggle_startup":
                    self.set_start_with_windows(not self.cfg["start_with_windows"])
                elif ev == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(30, self.poll)

    def _is_ours(self, hwnd):
        return win32.window_pid(hwnd) == os.getpid()

    def track_foreground(self):
        fg = win32.GetForegroundWindow()
        if fg and not self._is_ours(fg) and win32.window_class(fg) not in _SHELL_CLASSES:
            self.last_target = fg
            if self.bar.visible and self.bar.pinned:
                self._retarget(fg)  # pinned bar follows the chat you are in
        self.root.after(300, self.track_foreground)

    def _retarget(self, hwnd):
        """Point a pinned bar at hwnd; re-render {name} if the window/title changed."""
        process = win32.process_name(win32.window_pid(hwnd))
        title = win32.window_title(hwnd)
        if hwnd == self.target and (process, title) == getattr(self, "_target_key", None):
            return
        self.target, self._target_key = hwnd, (process, title)
        self.name = names.name_for(process, title)
        self.context = names.app_label(process)
        self.rendered = self._render()
        self.bar.refresh(self.rendered, self.context)

    def on_hotkey(self):
        fg = win32.GetForegroundWindow()
        if self.bar.visible:
            if self.bar.pinned and fg and not self._is_ours(fg):
                self.open_bar_for(fg)  # pinned: retarget + focus the bar for keyboard picks
            else:
                self.bar.hide()
            return
        if not fg or self._is_ours(fg):
            return  # one of our own windows is active; nothing to insert into
        self.open_bar_for(fg)

    def open_bar_from_tray(self):
        if self.bar.visible:
            return
        t = self.last_target
        if not t or not win32.IsWindow(t):
            self.tray.notify("Click into a text box in another app first, "
                             f"then press {self.cfg['hotkey']}.")
            return
        self.open_bar_for(t)

    def open_bar_for(self, hwnd):
        self.target = self.last_target = hwnd
        process = win32.process_name(win32.window_pid(hwnd))
        title = win32.window_title(hwnd)
        self._target_key = (process, title)
        debug(f"target: ({process!r}, {title!r})")
        self.name = names.name_for(process, title)
        self.context = names.app_label(process)
        self.show_bar()

    def _render(self):
        return [names.render(r, self.name) for r in self.cfg["replies"] if r.strip()]

    def show_bar(self):
        self.rendered = self._render()
        cx, cy = win32.cursor_pos()
        self.bar.show(self.rendered, cx, cy, press_enter=self.cfg["press_enter"],
                      context=self.context)

    def pick(self, index, shift):
        text = self.rendered[index]
        press_enter = self.cfg["press_enter"] != shift
        target = self.target
        debug(f"pick #{index + 1} press_enter={press_enter}")
        # Hand focus back while we are still the foreground process, then hide
        # (a pinned bar stays visible; it just gives focus back to the chat).
        win32.force_foreground(target)
        if not self.bar.pinned:
            self.bar.hide()
        inserter.insert(text, target, press_enter, self.owner_hwnd,
                        on_done=lambda ok: debug(f"insert {'ok' if ok else 'FAILED'}"))

    def add_reply(self, text):
        self.cfg["replies"].append(text)
        self.save()
        self.rendered = self._render()
        self.bar.refresh(self.rendered)
        self.settings.refresh()

    def set_start_with_windows(self, value):
        if startup.packaged:  # Store build: Windows owns the switch
            startup.open_startup_settings()
            return
        if not startup.set_enabled(bool(value)):
            self.tray.notify("Couldn't change the Start with Windows setting.")
        self.cfg["start_with_windows"] = startup.is_enabled()
        self.save()
        self.tray.refresh_menu()
        self.settings.refresh_options()

    def toggle_pin(self):
        self.set_keep_open(not self.cfg["keep_open"])

    def set_keep_open(self, value):
        self.cfg["keep_open"] = bool(value)
        self.save()
        self.bar.set_pinned(value)
        self.settings.refresh_options()

    def open_settings(self):
        self.bar.hide()
        self.settings.show()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    log.enabled = "--debug" in argv

    mutex = win32.CreateMutexW(None, False, MUTEX_NAME)
    if win32.get_last_error() == win32.ERROR_ALREADY_EXISTS:
        debug("already running; exiting")
        return 0

    debug(f"DPI awareness: {set_dpi_awareness()}")
    root = tk.Tk()
    root.withdraw()
    root.title("Quick Replies")

    app = App(root)
    app.start()
    # Ctrl+C in the console quits (signals are handled between Tk callbacks).
    signal.signal(signal.SIGINT, lambda *a: root.after(0, app.quit))
    debug(f"ready; settings at {config.default_path()}")
    root.mainloop()
    win32.CloseHandle(mutex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
