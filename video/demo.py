"""Record the staged walkthrough: the real app + a throwaway chat window, driven by script.

    .venv\\Scripts\\python.exe video\\demo.py

Each scene lasts as long as its narration clip (video/build/clips.json). Records the
primary monitor's work area (16:9 crop) with ffmpeg ddagrab to video/build/rec.mkv and
writes the scene timeline to video/build/timeline.json. Uses throwaway settings in
video/build/appdata, so your real replies/settings are untouched.

Before running: quit Quick Replies, turn on Do Not Disturb, and don't touch the PC.
"""
import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, ROOT)

APPDATA = os.path.join(BUILD, "appdata")
shutil.rmtree(APPDATA, ignore_errors=True)
os.makedirs(os.path.join(APPDATA, "QuickRepliesDesktop"))
os.environ["APPDATA"] = APPDATA  # throwaway settings for the demo

from app import main as appmain, names, startup, win32  # noqa: E402

# Demo-only: never touch the real Start-with-Windows entry (the throwaway settings say
# "off", and the app would otherwise sync the registry to that at startup).
startup.sync = lambda want: False
startup.set_enabled = lambda on: True

# Demo-only: the throwaway chat window is a python.exe window, not Slack/Discord, so make
# {name} and the "→ App" label behave as they do in a real Slack/Discord DM with Priya.
_orig_name_for, _orig_label = names.name_for, names.app_label
names.name_for = lambda p, t: ("Priya" if "Priya" in (t or "") and (p or "").lower()
                               .startswith("python") else _orig_name_for(p, t))
names.app_label = lambda p: "Chat" if (p or "").lower().startswith("python") else _orig_label(p)

LEAD = 0.25      # narration starts this long after its scene starts
TAIL = 0.55      # gap after a line before the next scene
OUTRO_RECORD = 5.5

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
KEYEVENTF_UNICODE = 0x0004
GWL_EXSTYLE, WS_EX_NOACTIVATE = -20, 0x08000000


# ---------------------------------------------------------------- safety guard
# Input may only ever go to the demo's own windows (this process + the test chat).
ALLOWED_PIDS = {os.getpid()}
RECORDER = []  # the ffmpeg process, so a failure can stop it


class UnsafeInput(RuntimeError):
    pass


def _owner(hwnd):
    return win32.window_pid(win32.root_hwnd(hwnd)) if hwnd else 0


def guard_focus(what):
    fg = win32.GetForegroundWindow()
    if _owner(fg) not in ALLOWED_PIDS:
        raise UnsafeInput(f"stopped before {what}: focus is on another app")


def guard_point(x, y, what):
    hwnd = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    if _owner(hwnd) not in ALLOWED_PIDS:
        raise UnsafeInput(f"stopped before {what}: another app is under the mouse")


# ---------------------------------------------------------------- input helpers
def _mouse(flags):
    inp = win32.INPUT()
    inp.type = win32.INPUT_MOUSE
    inp.mi = win32.MOUSEINPUT(0, 0, 0, flags, 0, 0)
    win32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(win32.INPUT))


def move(x, y, dur=0.45):
    sx, sy = win32.cursor_pos()
    steps = max(1, int(dur * 90))
    for i in range(1, steps + 1):
        t = i / steps
        e = 1 - (1 - t) ** 3
        user32.SetCursorPos(int(sx + (x - sx) * e), int(sy + (y - sy) * e))
        time.sleep(dur / steps)


def click(x=None, y=None, dur=0.45):
    if x is not None:
        move(x, y, dur)
        time.sleep(0.08)
    guard_point(*win32.cursor_pos(), "a click")
    _mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.06)
    _mouse(MOUSEEVENTF_LEFTUP)


def drag(x1, y1, x2, y2, dur=0.8):
    move(x1, y1, 0.35)
    time.sleep(0.1)
    guard_point(x1, y1, "a drag")
    _mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.1)
    move(x2, y2, dur)
    time.sleep(0.1)
    _mouse(MOUSEEVENTF_LEFTUP)


def keys(*events, check=True):
    if check and any(not up for _, up in events):
        guard_focus("a key press")
    win32.send_keys(list(events))


def tap(vk):
    keys((vk, False), (vk, True))


def hotkey():
    keys((0x11, False), (0x10, False), (0x20, False), (0x20, True), (0x10, True), (0x11, True))


def type_text(text, per_char=0.045):
    for ch in text:
        guard_focus("typing")
        arr = (win32.INPUT * 2)()
        for k, up in enumerate((0, win32.KEYEVENTF_KEYUP)):
            arr[k].type = win32.INPUT_KEYBOARD
            arr[k].ki = win32.KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | up, 0, 0)
        win32.SendInput(2, arr, ctypes.sizeof(win32.INPUT))
        time.sleep(per_char)


# ---------------------------------------------------------------- stage
class Stage:
    def __init__(self):
        appmain.set_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = appmain.App(self.root)
        self.calls = queue.Queue()
        left, top, right, bottom = win32.work_area_at(1, 1)
        w, h = right - left, bottom - top
        if w * 9 > h * 16:
            rh, rw = h, h * 16 // 9
        else:
            rw, rh = w, w * 9 // 16
        rw, rh = rw - rw % 2, rh - rh % 2
        self.region = (left + (w - rw) // 2, top + (h - rh) // 2, rw, rh)
        self._build_backdrop()

    def _build_backdrop(self):
        x, y, w, h = self.region
        b = self.backdrop = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.geometry(f"{w}x{h}+{x}+{y}")
        b.attributes("-topmost", True)
        self.canvas = tk.Canvas(b, width=w, height=h, highlightthickness=0, bg="#ff00ff")
        self.canvas.pack()
        self.keycap = None

    def paint_backdrop(self):
        c = self.canvas
        c.delete("all")
        w, h = self.region[2], self.region[3]
        top, bottom = (0x14, 0x17, 0x2e), (0x3b, 0x27, 0x6e)
        for i in range(0, h, 4):
            t = i / h
            col = "#" + "".join(f"{round(a + (b - a) * t):02x}" for a, b in zip(top, bottom))
            c.create_rectangle(0, i, w, i + 4, fill=col, outline="")
        s = self.root.winfo_fpixels("1i") / 96
        c.create_text(w - int(28 * s), h - int(22 * s), anchor="se", fill="#8f86c9",
                      text="Quick Replies for Windows", font=("Segoe UI Variable Text", 11))
        self.backdrop.update()

    def lock_backdrop(self):
        """Keep the backdrop above every normal window (so nothing else can show up in the
        recording) but never let it take focus (so Windows never activates it)."""
        hwnd = win32.root_hwnd(self.backdrop.winfo_id())
        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        self.backdrop.attributes("-topmost", True)

    def front(self, top):
        """Put one of our windows above the backdrop and give it focus."""
        top.attributes("-topmost", True)
        top.lift()
        top.update()
        win32.force_foreground(win32.root_hwnd(top.winfo_id()))
        top.focus_force()

    def show_keycap(self, text, seconds=1.6):
        """On-screen badge of the keys being pressed (bottom-left)."""
        c = self.canvas
        if self.keycap:
            for item in self.keycap:
                c.delete(item)
        s = self.root.winfo_fpixels("1i") / 96
        font = ("Cascadia Mono", 14, "bold")
        x, y = int(36 * s), self.region[3] - int(34 * s)
        t = c.create_text(x + int(18 * s), y, anchor="w", text=text, fill="#e8eef8", font=font)
        x1, y1, x2, y2 = c.bbox(t)
        r = c.create_rectangle(x1 - int(16 * s), y1 - int(9 * s), x2 + int(16 * s),
                               y2 + int(9 * s), fill="#0b0f19", outline="#22d3ee", width=2)
        c.tag_raise(t)
        self.keycap = (r, t)
        self.root.after(int(seconds * 1000), lambda items=(r, t): [c.delete(i) for i in items])

    # Run fn on the Tk thread and return its result (Tk isn't thread-safe).
    def call(self, fn):
        box = {}
        done = threading.Event()
        self.calls.put((fn, box, done))
        done.wait(5)
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def _pump(self):
        try:
            while True:
                fn, box, done = self.calls.get_nowait()
                try:
                    box["result"] = fn()
                except Exception as e:  # surface in the driver thread
                    box["error"] = e
                done.set()
        except queue.Empty:
            pass
        # The test chat is topmost (to sit above the backdrop), so it can cover the
        # bar when it gets focus. Keep a visible bar above it, without activating it.
        self._tick = getattr(self, "_tick", 0) + 1
        if self._tick % 5 == 0 and self.app.bar.visible:
            user32.SetWindowPos(self.app.bar.hwnd(), wintypes.HWND(-1), 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
        try:
            self.root.after(10, self._pump)
        except tk.TclError:
            pass  # app.quit() destroyed the root


def center(widget):
    return (widget.winfo_rootx() + widget.winfo_width() // 2,
            widget.winfo_rooty() + widget.winfo_height() // 2)


def find_label(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and child.cget("text") == text:
            return child
        found = find_label(child, text)
        if found:
            return found
    return None


# ---------------------------------------------------------------- the script
def run(stage, clips, chat_proc, ready_path, done_path):
    st, app = stage, stage.app
    dur = {c["id"]: c["seconds"] for c in clips}
    timeline = []
    t0 = None

    def now():
        return time.monotonic() - t0

    def scene(seg_id):
        timeline.append({"id": seg_id, "start": round(now(), 3)})
        return now()

    def at(start, offset):
        delay = start + offset - now()
        if delay > 0:
            time.sleep(delay)

    def finish(start, seg_id):
        at(start, LEAD + dur[seg_id] + TAIL)

    def bar_row(i):
        return st.call(lambda: center(app.bar.rows[i]))

    def chat_fg():
        if win32.GetForegroundWindow() != chat_hwnd:
            win32.force_foreground(chat_hwnd)
            time.sleep(0.15)

    # Wait for the chat window
    for _ in range(100):
        if os.path.exists(ready_path):
            break
        time.sleep(0.1)
    info = json.load(open(ready_path))
    chat_hwnd = info["hwnd"]
    ALLOWED_PIDS.add(win32.window_pid(chat_hwnd))
    bx, by, bw, bh = info["box"]
    st.call(st.lock_backdrop)
    box_pt = (bx + bw // 3, by + bh // 2)
    user32.SetCursorPos(st.region[0] + st.region[2] // 2, st.region[1] + st.region[3] // 2)

    # Start recording, then the sync flash (magenta -> backdrop) marks t0.
    x, y, w, h = st.region
    rec = os.path.join(BUILD, "rec.mkv")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
         f"ddagrab=output_idx=0:framerate=30:offset_x={x}:offset_y={y}:"
         f"video_size={w}x{h}:draw_mouse=1",
         "-vf", "hwdownload,format=bgra,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", rec],
        stdin=subprocess.PIPE)
    RECORDER.append(ff)
    time.sleep(2.5)
    st.call(st.paint_backdrop)
    t0 = time.monotonic()
    # Chat above the (topmost) backdrop, then focused.
    user32.SetWindowPos(chat_hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
    win32.force_foreground(chat_hwnd)
    time.sleep(0.6)

    # intro: the chat with Priya's message
    s = scene("intro")
    at(s, 1.6)
    click(*box_pt, dur=0.9)
    finish(s, "intro")

    # hotkey: press Ctrl+Shift+Space, the bar appears
    s = scene("hotkey")
    at(s, 2.3)
    chat_fg()
    st.call(lambda: st.show_keycap("Ctrl + Shift + Space"))
    hotkey()
    finish(s, "hotkey")

    # name: hover "Hi Priya"
    s = scene("name")
    at(s, 1.0)
    move(*bar_row(1), dur=0.6)
    at(s, 4.6)
    move(*bar_row(0), dur=0.6)
    finish(s, "name")

    # insert: click it, it's typed into the chat; Enter sends
    s = scene("insert")
    at(s, 1.6)
    click(*bar_row(0), dur=0.3)
    at(s, 4.3)
    chat_fg()
    st.call(lambda: st.show_keycap("Enter", 1.2))
    tap(win32.VK_RETURN)
    finish(s, "insert")

    # send: hotkey, hold Shift (badge flips), Shift+2 inserts and sends
    s = scene("send")
    at(s, 0.3)
    move(*box_pt, dur=0.4)
    chat_fg()
    st.call(lambda: st.show_keycap("Ctrl + Shift + Space", 1.2))
    hotkey()
    at(s, 2.6)
    keys((win32.VK_SHIFT, False))
    st.call(lambda: st.show_keycap("Shift", 2.2))
    at(s, 5.0)
    st.call(lambda: st.show_keycap("Shift + 2", 1.4))
    keys((0x32, False), (0x32, True))
    time.sleep(0.15)
    keys((win32.VK_SHIFT, True))
    finish(s, "send")

    # pin: open, pin, insert two replies, drag the bar
    s = scene("pin")
    at(s, 0.2)
    chat_fg()
    st.call(lambda: st.show_keycap("Ctrl + Shift + Space", 1.0))
    hotkey()
    time.sleep(0.5)
    click(*st.call(lambda: center(app.bar.pin_label)), dur=0.5)
    at(s, 1.9)
    click(*bar_row(2), dur=0.4)
    time.sleep(0.6)
    chat_fg()
    tap(win32.VK_RETURN)
    at(s, 3.1)
    hx, hy = st.call(lambda: (app.bar.header.winfo_rootx() + app.bar.header.winfo_width() // 3,
                              app.bar.header.winfo_rooty() + app.bar.header.winfo_height() // 2))
    drag(hx, hy, hx + int(w * 0.16), hy - int(h * 0.04), dur=0.9)
    finish(s, "pin")

    # settings: add a reply, look around Settings
    s = scene("settings")
    at(s, 0.2)
    gear = st.call(lambda: center(find_label(app.bar.top, "⚙")))
    click(*gear, dur=0.5)
    for _ in range(40):  # the click is handled by Tk after this returns; wait for it
        if st.call(lambda: app.settings.is_open):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Settings did not open")
    time.sleep(0.2)
    st.call(lambda: st.front(app.settings.top))
    time.sleep(0.2)
    click(*st.call(lambda: center(app.settings.add_entry)), dur=0.5)
    time.sleep(0.2)
    type_text("Running 5 min late, start without me")
    click(*st.call(lambda: center(find_label(app.settings.top, "+ Add"))), dur=0.4)
    at(s, 4.6)
    move(*st.call(lambda: center(app.settings.hk_canvas)), dur=0.6)
    at(s, 5.8)
    close_btn = st.call(lambda: center(find_label(app.settings.top, "Close")))
    move(*close_btn, dur=0.5)
    finish(s, "settings")
    click()

    # outro: use the new reply, close the bar, end on the chat
    s = scene("outro")
    at(s, 0.3)
    move(*box_pt, dur=0.4)
    chat_fg()
    hotkey()
    time.sleep(0.7)
    if st.call(lambda: len(app.bar.rows)) < 5:
        raise RuntimeError("the reply added in Settings is missing from the bar")
    click(*bar_row(4), dur=0.5)
    time.sleep(0.6)
    chat_fg()
    tap(win32.VK_RETURN)
    at(s, 3.2)
    click(*st.call(lambda: center(find_label(app.bar.top, "✕"))), dur=0.5)
    time.sleep(0.2)
    move(st.region[0] + int(w * 0.8), st.region[1] + int(h * 0.55), dur=0.8)
    at(s, OUTRO_RECORD)
    end = now()

    ff.stdin.write(b"q")
    ff.stdin.flush()
    ff.wait(20)
    open(done_path, "w").close()
    chat_proc.wait(10)
    with open(os.path.join(BUILD, "timeline.json"), "w") as f:
        json.dump({"region": st.region, "lead": LEAD, "end": round(end, 3),
                   "outro_record": OUTRO_RECORD, "scenes": timeline}, f, indent=2)
    print("recorded", rec, f"({end:.1f}s after sync)")


def main():
    clips_path = os.path.join(BUILD, "clips.json")
    if not os.path.exists(clips_path):
        sys.exit("Run video/split_audio.py first.")
    clips = json.load(open(clips_path))
    stage = Stage()
    if not stage.app.cfg:
        sys.exit("no config")
    stage.app.start()
    if not stage.app.hotkey_ok:
        stage.root.destroy()
        sys.exit("Ctrl+Shift+Space is taken. Quit Quick Replies (tray icon > Quit) and retry.")
    stage.root.after(10, stage._pump)

    x, y, w, h = stage.region
    cw, ch = int(w * 0.5), int(h * 0.78)
    cx, cy = x + int(w * 0.09), y + int(h * 0.1)
    ready = os.path.join(BUILD, "chat_ready.json")
    done = os.path.join(BUILD, "chat_done.flag")
    for p in (ready, done):
        if os.path.exists(p):
            os.remove(p)
    chat = subprocess.Popen([sys.executable, os.path.join(HERE, "chat.py"),
                             str(cx), str(cy), str(cw), str(ch), ready, done],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    result = {}

    def driver():
        try:
            run(stage, clips, chat, ready, done)
        except Exception as e:
            result["error"] = e
        finally:
            for vk in (win32.VK_SHIFT, win32.VK_CONTROL):  # never leave a key held
                keys((vk, True), check=False)
            if "error" in result:
                # Stop the recorder and delete the partial file: after a failure it may
                # contain things that aren't part of the demo.
                for ff in RECORDER:
                    if ff.poll() is None:
                        ff.kill()
                        ff.wait(10)
                rec = os.path.join(BUILD, "rec.mkv")
                if os.path.exists(rec):
                    os.remove(rec)
            stage.calls.put((stage.app.quit, {}, threading.Event()))

    threading.Thread(target=driver, daemon=True).start()
    stage.root.mainloop()
    if os.path.exists(ready):
        open(done, "w").close()
    if "error" in result:
        raise result["error"]


if __name__ == "__main__":
    main()
