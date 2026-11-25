"""Tray icon (pystray) on its own thread. Menu clicks are put on the app's event queue;
this module never touches Tk."""
import threading

import pystray
from PIL import Image

from app.config import asset_path
from app.log import debug


class Tray:
    def __init__(self, events, is_startup_on):
        """is_startup_on() -> bool is read by the menu to draw the ✓ (just reads a flag)."""
        self.events = events
        self.is_startup_on = is_startup_on
        self.icon = None
        self._ready = threading.Event()

    def _post(self, name):
        return lambda icon, item: self.events.put(name)

    def start(self, tooltip):
        menu = pystray.Menu(
            pystray.MenuItem("Open bar", self._post("open_bar"), default=True),
            pystray.MenuItem("Settings", self._post("settings")),
            pystray.MenuItem("Start with Windows", self._post("toggle_startup"),
                             checked=lambda item: self.is_startup_on()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._post("quit")),
        )
        image = Image.open(asset_path("icon128.png"))
        self.icon = pystray.Icon("QuickReplies", image, tooltip, menu)

        def setup(icon):
            icon.visible = True
            self._ready.set()

        threading.Thread(target=self.icon.run, kwargs={"setup": setup},
                         name="tray", daemon=True).start()

    def refresh_menu(self):
        if self.icon:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def set_tooltip(self, text):
        if self.icon:
            self.icon.title = text

    def notify(self, message):
        if self.icon and self._ready.wait(3):
            try:
                self.icon.notify(message, "Quick Replies")
            except Exception as e:  # notifications are best-effort
                debug(f"tray notify failed: {e}")

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
