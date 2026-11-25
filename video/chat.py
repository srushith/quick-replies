"""A plain, generic chat window used as the insert target in the walkthrough.

    python video/chat.py <x> <y> <w> <h> <ready.json> <done.flag>

It's its own process (Quick Replies ignores its own windows). Enter sends the message
box as a bubble. Writes ready.json (hwnd + message box position) once shown, and exits
when done.flag appears.
"""
import ctypes
import json
import os
import sys
import tkinter as tk
import tkinter.font as tkfont

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

x, y, w, h = (int(v) for v in sys.argv[1:5])
READY, DONE = sys.argv[5], sys.argv[6]

BG = "#f6f7fb"
PANEL = "#ffffff"
LINE = "#e3e6ee"
INK = "#1f2330"
SOFT = "#6b7385"
THEIRS = "#eceff5"
MINE = "#4f46e5"

root = tk.Tk()
root.title("Chat — Priya Sharma")
root.configure(bg=BG)
root.geometry(f"{w}x{h}+{x}+{y}")
fams = set(tkfont.families())
ui = "Segoe UI Variable Text" if "Segoe UI Variable Text" in fams else "Segoe UI"
f_name = tkfont.Font(family=ui, size=13, weight="bold")
f_status = tkfont.Font(family=ui, size=9)
f_msg = tkfont.Font(family=ui, size=11)
f_avatar = tkfont.Font(family=ui, size=13, weight="bold")
scale = root.winfo_fpixels("1i") / 96


def px(n):
    return int(n * scale)


# Header
head = tk.Frame(root, bg=PANEL, height=px(64))
head.pack(fill="x")
head.pack_propagate(False)
av = tk.Canvas(head, width=px(40), height=px(40), bg=PANEL, highlightthickness=0)
av.pack(side="left", padx=(px(18), px(12)))
av.create_oval(1, 1, px(40) - 1, px(40) - 1, fill="#f59e0b", outline="")
av.create_text(px(20), px(20), text="P", fill="white", font=f_avatar)
info = tk.Frame(head, bg=PANEL)
info.pack(side="left")
tk.Label(info, text="Priya Sharma", font=f_name, bg=PANEL, fg=INK).pack(anchor="w")
tk.Label(info, text="● Active now", font=f_status, bg=PANEL, fg="#16a34a").pack(anchor="w")
tk.Frame(root, bg=LINE, height=1).pack(fill="x")

# Messages
msgs = tk.Frame(root, bg=BG)
msgs.pack(fill="both", expand=True, padx=px(18), pady=px(12))


def bubble(text, mine):
    row = tk.Frame(msgs, bg=BG)
    row.pack(fill="x", pady=px(4))
    lbl = tk.Label(row, text=text, font=f_msg, wraplength=int(w * 0.6), justify="left",
                   bg=MINE if mine else THEIRS, fg="white" if mine else INK,
                   padx=px(14), pady=px(8))
    lbl.pack(side="right" if mine else "left")


bubble("Hey! Did you get a chance to look at the deck I sent?", mine=False)

# Composer
tk.Frame(root, bg=LINE, height=1).pack(fill="x")
comp = tk.Frame(root, bg=PANEL)
comp.pack(fill="x")
box = tk.Text(comp, height=2, font=f_msg, bg="#f1f3f8", fg=INK, relief="flat", bd=0,
              wrap="word", padx=px(12), pady=px(10), insertbackground=INK,
              highlightthickness=1, highlightbackground=LINE, highlightcolor=MINE)
box.pack(fill="x", padx=px(16), pady=px(14))
HINT = "Message Priya"


def send(e=None):
    text = box.get("1.0", "end-1c").strip()
    if text:
        bubble(text, mine=True)
    box.delete("1.0", "end")
    return "break"


box.bind("<Return>", send)
box.bind("<KP_Enter>", send)


def ready():
    root.attributes("-topmost", True)  # stays above the demo's backdrop
    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
    info = {"hwnd": hwnd,
            "box": [box.winfo_rootx(), box.winfo_rooty(), box.winfo_width(), box.winfo_height()]}
    tmp = READY + ".tmp"
    with open(tmp, "w") as f:
        json.dump(info, f)
    os.replace(tmp, READY)
    box.focus_set()


def watch_done():
    if os.path.exists(DONE):
        root.destroy()
        return
    root.after(200, watch_done)


root.after(500, ready)
root.after(200, watch_done)
root.mainloop()
