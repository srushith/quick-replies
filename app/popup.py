"""The reply bar: a small borderless, always-on-top popup next to the mouse pointer.

Look: dark "glass" card, Windows 11 rounded corners with a cyan hairline (DWM),
cyan->violet gradient accents, keycap number chips, an animated selection bar,
a live insert/send badge that follows Shift, and a fade + slide-in on open.
"""
import tkinter as tk
import tkinter.font as tkfont

from app import win32
from app.log import debug

# ---------------------------------------------------------------- theme
CARD = "#0b0f19"
SEL = "#151e31"
SEL_GLOW = "#0c3442"
FG = "#e8eef8"
FG_SOFT = "#b4c0d3"
MUTED = "#66758c"
DIM = "#2a3548"
CYAN = "#22d3ee"
VIOLET = "#a78bfa"
ENTRY_BG = "#070a12"
FALLBACK_BORDER = "#1d4f60"
DWM_BORDER = (0x1f, 0x7a, 0x94)  # glowing cyan hairline on Windows 11
ALPHA = 0.985

MAX_DISPLAY = 48
SHIFT_MASK = 0x0001
VK_1, VK_9 = 0x31, 0x39
VK_NUMPAD1, VK_NUMPAD9 = 0x61, 0x69


def place(cx, cy, w, h, area, gap=12):
    """Top-left for a w*h popup just below-right of the pointer, kept inside area.

    area = (left, top, right, bottom). Flips to the left/above the pointer if it
    would overflow, then clamps. Pure function, unit-tested.
    """
    left, top, right, bottom = area
    x, y = cx + gap, cy + gap
    if x + w > right:
        x = cx - gap - w
    if y + h > bottom:
        y = cy - gap - h
    x = max(left, min(x, right - w))
    y = max(top, min(y, bottom - h))
    return x, y


def display_text(text):
    t = " ".join(text.split())
    return t if len(t) <= MAX_DISPLAY else t[: MAX_DISPLAY - 1] + "…"


def mix(a, b, t):
    """Blend two '#rrggbb' colors, t in [0, 1]."""
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def ease_out(t):
    return 1 - (1 - t) ** 3


def _pick_font(families, *candidates):
    for c in candidates:
        if c in families:
            return c
    return candidates[-1]


def rrect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class ReplyBar:
    def __init__(self, root, on_pick, on_add, on_settings=None, on_pin=None):
        """on_pick(index, shift_held) / on_add(text) / on_settings() / on_pin() run on the
        Tk thread. on_pin toggles "keep open"; the owner calls set_pinned() with the result."""
        self.root = root
        self.on_pick = on_pick
        self.on_add = on_add
        self.on_settings = on_settings
        self.on_pin = on_pin
        self.scale = root.winfo_fpixels("1i") / 96.0

        fams = set(tkfont.families(root))
        ui = _pick_font(fams, "Segoe UI Variable Text", "Segoe UI")
        mono = _pick_font(fams, "Cascadia Mono", "Consolas")
        self.f_text = tkfont.Font(root, family=ui, size=10)
        self.f_text_sel = tkfont.Font(root, family=ui, size=10, weight="bold")
        self.f_key = tkfont.Font(root, family=mono, size=8, weight="bold")
        self.f_tag = tkfont.Font(root, family=mono, size=7, weight="bold")
        self.f_ui = tkfont.Font(root, family=ui, size=9)

        self.items = []
        self.rows = []           # canvases, one per reply
        self.sel = 0
        self.visible = False
        self.press_enter = False
        self.shift = False
        self.context = ""
        self.width = self.px(300)
        self._focus_job = None
        self._anim_job = None
        self._sel_job = None
        self._anchor = (0, 0)
        self._adding = False
        self._styled = False
        self.pinned = False
        self._drag = None
        self._manual = None

        self.top = tk.Toplevel(root, bg=CARD)
        self.top.withdraw()
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)

        # Fallback hairline border (hidden behind DWM's border on Windows 11).
        self.frame = tk.Frame(self.top, bg=FALLBACK_BORDER)
        self.frame.pack(fill="both", expand=True)
        self.card = tk.Frame(self.frame, bg=CARD, padx=self.px(8), pady=self.px(8))
        self.card.pack(padx=1, pady=1, fill="both", expand=True)

        self.header = tk.Canvas(self.card, bg=CARD, highlightthickness=0, height=self.px(22))
        self.header.pack(fill="x")
        self.rule = tk.Canvas(self.card, bg=CARD, highlightthickness=0, height=self.px(2))
        self.rule.pack(fill="x", pady=(self.px(4), self.px(6)))
        self.list_frame = tk.Frame(self.card, bg=CARD)
        self.list_frame.pack(fill="x")

        self.add_frame = tk.Frame(self.card, bg=CARD)
        self.add_entry = tk.Entry(
            self.add_frame, font=self.f_text, bg=ENTRY_BG, fg=FG, insertbackground=CYAN,
            relief="flat", bd=0, highlightthickness=1, highlightbackground=DIM,
            highlightcolor=CYAN, selectbackground=SEL, selectforeground=FG)
        self.add_entry.pack(fill="x", padx=self.px(2), pady=(self.px(6), 0), ipady=self.px(5))
        self.add_entry.bind("<Return>", self._commit_add)
        self.add_entry.bind("<KP_Enter>", self._commit_add)
        self.add_entry.bind("<Escape>", self._cancel_add)

        self.footer_rule = tk.Canvas(self.card, bg=CARD, highlightthickness=0, height=1)
        self.footer_rule.pack(fill="x", pady=(self.px(8), self.px(5)))
        footer = tk.Frame(self.card, bg=CARD)
        footer.pack(fill="x")
        self._footer_button(footer, "+ add", self._start_add, "left", color=CYAN)
        self._footer_button(footer, "✕", self.hide, "right")
        self._footer_button(footer, "⚙", self._settings, "right",
                            enabled=on_settings is not None)
        self.pin_label = tk.Label(footer, font=self.f_ui, bg=CARD, padx=self.px(6),
                                  pady=self.px(1), cursor="hand2")
        self.pin_label.pack(side="right")
        self.pin_label.bind("<Button-1>", lambda e: self.on_pin and self.on_pin())
        self.pin_label.bind("<Enter>", lambda e: self.pin_label.configure(bg=SEL))
        self.pin_label.bind("<Leave>", lambda e: self.pin_label.configure(bg=CARD))
        self._draw_pin()
        tk.Label(footer, text="↑↓ ⏎ · ⇧ send", font=self.f_tag, bg=CARD,
                 fg="#46536a").pack(side="right", padx=self.px(4))

        # Drag the bar by its header (handy when pinned).
        self.header.configure(cursor="fleur")
        self.header.bind("<ButtonPress-1>", self._drag_start)
        self.header.bind("<B1-Motion>", self._drag_move)

        self.top.bind("<KeyPress>", self._on_key)
        self.top.bind("<KeyRelease>", self._on_key_release)
        self.top.bind("<FocusOut>", self._on_focus_out)
        self.top.bind("<FocusIn>", self._on_focus_in)

    def px(self, n):
        return int(round(n * self.scale))

    # ------------------------------------------------------------ building
    def _footer_button(self, parent, text, cmd, side, enabled=True, color=MUTED):
        fg = color if enabled else DIM
        lbl = tk.Label(parent, text=text, font=self.f_ui, bg=CARD, fg=fg,
                       padx=self.px(6), pady=self.px(1), cursor="hand2" if enabled else "")
        lbl.pack(side=side)
        if enabled:
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e: lbl.configure(fg=FG, bg=SEL))
            lbl.bind("<Leave>", lambda e: lbl.configure(fg=fg, bg=CARD))
        return lbl

    def _measure_width(self):
        texts = [display_text(t) for t in self.items] or ["No replies yet — press + add"]
        text_w = max(self.f_text_sel.measure(t) for t in texts)
        badge_w = self.f_tag.measure("⏎ SEND") + self.px(18)
        w = self.px(46) + text_w + badge_w
        return max(self.px(300), min(w, self.px(480)))

    def _build_rows(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.rows = []
        self.width = self._measure_width()
        if not self.items:
            tk.Label(self.list_frame, text="No replies yet — press + add", font=self.f_text,
                     bg=CARD, fg=MUTED, pady=self.px(8)).pack(anchor="w", padx=self.px(8))
        for i in range(len(self.items)):
            c = tk.Canvas(self.list_frame, bg=CARD, highlightthickness=0,
                          width=self.width, height=self.px(34), cursor="hand2")
            c.pack(fill="x", pady=(0, self.px(2)))
            c.bind("<Button-1>", lambda e, i=i: self._pick(i, bool(e.state & SHIFT_MASK)))
            c.bind("<Enter>", lambda e, i=i: self._select(i) if i != self.sel else None)
            self.rows.append(c)
        self.sel = min(self.sel, max(len(self.items) - 1, 0))
        for i in range(len(self.rows)):
            self._draw_row(i, 1.0)
        self._draw_chrome()

    def _draw_chrome(self):
        w = self.width
        h = self.header
        h.delete("all")
        h.configure(width=w)
        mid = self.px(11)
        # Small gradient diamond mark.
        s = self.px(5)
        x0 = self.px(9)
        for k in range(s, 0, -1):
            t = 1 - k / s
            h.create_polygon(x0, mid - k, x0 + k, mid, x0, mid + k, x0 - k, mid,
                             fill=mix(CYAN, VIOLET, t), outline="")
        h.create_text(self.px(22), mid, text="QUICK REPLIES", anchor="w",
                      font=self.f_tag, fill=FG_SOFT)
        if self.context:
            right = w - self.px(4)
            h.create_text(right, mid, text=self.context, anchor="e",
                          font=self.f_ui, fill=FG)
            arrow_x = right - self.f_ui.measure(self.context) - self.px(6)
            h.create_text(arrow_x, mid, text="→", anchor="e", font=self.f_ui, fill=CYAN)

        # Gradient rule under the header: cyan -> violet -> fade out.
        r = self.rule
        r.delete("all")
        r.configure(width=w)
        steps = max(w // 3, 1)
        for k in range(steps):
            t = k / steps
            col = mix(CYAN, VIOLET, t / 0.6) if t < 0.6 else mix(VIOLET, CARD, (t - 0.6) / 0.4)
            r.create_rectangle(k * 3, 0, k * 3 + 3, self.px(2), fill=col, outline="")
        fr = self.footer_rule
        fr.delete("all")
        fr.configure(width=w)
        fr.create_rectangle(0, 0, w, 1, fill="#161e2d", outline="")

    def _draw_row(self, i, progress):
        """Draw row i. progress (0..1) animates the selection bar growing in."""
        c = self.rows[i]
        c.delete("all")
        w, h = self.width, self.px(34)
        selected = i == self.sel
        if selected:
            rrect(c, 0, 0, w, h, self.px(8), fill=SEL, outline="")
            grow = ease_out(progress)
            half = (h / 2 - self.px(7)) * grow + self.px(2)
            cy = h / 2
            rrect(c, 0, cy - half - self.px(2), self.px(7), cy + half + self.px(2),
                  self.px(3), fill=SEL_GLOW, outline="")
            rrect(c, 0, cy - half, self.px(3), cy + half, self.px(2), fill=CYAN, outline="")

        # Keycap chip with the number.
        kx, ks = self.px(14), self.px(20)
        ky = (h - ks) / 2
        label = str(i + 1) if i < 9 else "·"
        if selected:
            rrect(c, kx, ky, kx + ks, ky + ks, self.px(5), fill=mix(SEL, CYAN, 0.12),
                  outline=CYAN)
        else:
            rrect(c, kx, ky, kx + ks, ky + ks, self.px(5), fill=CARD, outline=DIM)
        c.create_text(kx + ks / 2, h / 2, text=label, font=self.f_key,
                      fill=CYAN if selected else MUTED)

        c.create_text(self.px(44), h / 2, text=display_text(self.items[i]), anchor="w",
                      font=self.f_text_sel if selected else self.f_text,
                      fill=FG if selected else FG_SOFT)

        if selected:
            send = self.press_enter != self.shift
            tag = "⏎ SEND" if send else "INSERT"
            color = VIOLET if send else MUTED
            tw = self.f_tag.measure(tag)
            bx2 = w - self.px(10)
            bx1 = bx2 - tw - self.px(12)
            by1, by2 = h / 2 - self.px(8), h / 2 + self.px(8)
            rrect(c, bx1, by1, bx2, by2, self.px(8), fill=mix(SEL, color, 0.14),
                  outline=mix(SEL, color, 0.55))
            c.create_text((bx1 + bx2) / 2, h / 2, text=tag, font=self.f_tag, fill=color)

    def _select(self, i):
        if not self.rows:
            return
        old, self.sel = self.sel, i
        if 0 <= old < len(self.rows) and old != i:
            self._draw_row(old, 1.0)
        if self._sel_job:
            self.top.after_cancel(self._sel_job)
            self._sel_job = None
        self._animate_sel(0)

    def _animate_sel(self, step, steps=6):
        self._sel_job = None
        if not (0 <= self.sel < len(self.rows)):
            return
        self._draw_row(self.sel, (step + 1) / steps)
        if step + 1 < steps:
            self._sel_job = self.top.after(12, self._animate_sel, step + 1, steps)

    def _redraw_selected(self):
        if 0 <= self.sel < len(self.rows):
            self._draw_row(self.sel, 1.0)

    # ------------------------------------------------------------ show / hide
    def show(self, items, cx, cy, press_enter=False, context=""):
        """items: rendered reply strings ({name} already replaced). cx, cy: pointer.

        If the bar is already visible (pinned), it stays where it is: the content is
        updated and it takes keyboard focus.
        """
        self.press_enter = press_enter
        self.shift = win32.is_down(win32.VK_SHIFT)  # still held from the hotkey
        if self.visible:
            self.refresh(items, context)
            self._take_focus()
            return
        self.items = list(items)
        self.sel = 0
        self.context = context
        self._anchor = (cx, cy)
        self._manual = None
        self._cancel_add()
        self._build_rows()
        x, y = self._reposition()
        self.top.attributes("-alpha", 0.0)
        self.top.deiconify()
        self.top.lift()
        self.top.attributes("-topmost", True)
        self.top.update()
        if not self._styled:
            self._styled = win32.style_popup(self.hwnd(), DWM_BORDER)
            if self._styled:
                self.frame.configure(bg=CARD)  # DWM draws the border instead
        self.visible = True
        self._take_focus()
        self._animate_in(x, y, 0)

    def _animate_in(self, x, y, step, steps=8):
        self._anim_job = None
        if not self.visible:
            return
        t = ease_out((step + 1) / steps)
        offset = round(self.px(10) * (1 - t))
        self.top.geometry(f"+{x}+{y + offset}")
        self.top.attributes("-alpha", ALPHA * t)
        if step + 1 < steps:
            self._anim_job = self.top.after(14, self._animate_in, x, y, step + 1, steps)

    def _reposition(self):
        self.top.update_idletasks()
        w = self.top.winfo_reqwidth()
        h = self.top.winfo_reqheight()
        if self._manual:  # user dragged the bar: keep it there, just keep it on-screen
            mx, my = self._manual
            area = win32.work_area_at(mx + w // 2, my + h // 2)
            x, y = mx, my
            if area:
                x = max(area[0], min(x, area[2] - w))
                y = max(area[1], min(y, area[3] - h))
        else:
            cx, cy = self._anchor
            area = win32.work_area_at(cx, cy) or (0, 0, self.top.winfo_screenwidth(),
                                                  self.top.winfo_screenheight())
            x, y = place(cx, cy, w, h, area, gap=self.px(12))
        self.top.geometry(f"{w}x{h}+{x}+{y}")
        return x, y

    # ------------------------------------------------------------ pin / drag
    def set_pinned(self, pinned):
        self.pinned = bool(pinned)
        self._draw_pin()

    def _draw_pin(self):
        if self.pinned:
            self.pin_label.configure(text="● pinned", fg=CYAN)
        else:
            self.pin_label.configure(text="○ pin", fg=MUTED)

    def _drag_start(self, e):
        self._drag = (e.x_root - self.top.winfo_rootx(), e.y_root - self.top.winfo_rooty())

    def _drag_move(self, e):
        if not self._drag:
            return
        if self._anim_job:
            self.top.after_cancel(self._anim_job)
            self._anim_job = None
            self.top.attributes("-alpha", ALPHA)
        x, y = e.x_root - self._drag[0], e.y_root - self._drag[1]
        self._manual = (x, y)
        self.top.geometry(f"+{x}+{y}")

    def hwnd(self):
        return win32.root_hwnd(self.top.winfo_id())

    def _take_focus(self):
        hwnd = self.hwnd()
        if not win32.force_foreground(hwnd):
            # Last resort for the foreground lock: an Alt tap counts as user input.
            debug("SetForegroundWindow refused; tapping Alt and retrying")
            win32.send_keys([(win32.VK_MENU, False), (win32.VK_MENU, True)])
            win32.force_foreground(hwnd)
        self.top.focus_force()

    def hide(self):
        for job in ("_focus_job", "_anim_job", "_sel_job"):
            if getattr(self, job):
                self.top.after_cancel(getattr(self, job))
                setattr(self, job, None)
        if self.visible:
            self.visible = False
            self.top.withdraw()
            self.top.update_idletasks()

    # ------------------------------------------------------------ events
    def _pick(self, i, shift):
        if 0 <= i < len(self.items):
            self.on_pick(i, shift)

    def _set_shift(self, down):
        if down != self.shift:
            self.shift = down
            self._redraw_selected()

    def _on_key(self, e):
        if e.widget is self.add_entry:
            return
        shift = bool(e.state & SHIFT_MASK)
        ks = e.keysym
        if ks in ("Shift_L", "Shift_R"):
            self._set_shift(True)
        elif ks == "Escape":
            self.hide()
        elif ks in ("Return", "KP_Enter"):
            self._pick(self.sel, shift)
        elif ks == "Up" and self.items:
            self._select((self.sel - 1) % len(self.items))
        elif ks == "Down" and self.items:
            self._select((self.sel + 1) % len(self.items))
        elif VK_1 <= e.keycode <= VK_9:  # keycode is the Windows VK; works with Shift held
            self._pick(e.keycode - VK_1, shift)
        elif VK_NUMPAD1 <= e.keycode <= VK_NUMPAD9:
            self._pick(e.keycode - VK_NUMPAD1, shift)
        return "break"

    def _on_key_release(self, e):
        if e.keysym in ("Shift_L", "Shift_R"):
            self._set_shift(win32.is_down(win32.VK_SHIFT))

    def _on_focus_in(self, e):
        if self._focus_job:
            self.top.after_cancel(self._focus_job)
            self._focus_job = None

    def _on_focus_out(self, e):
        if self._focus_job:
            self.top.after_cancel(self._focus_job)
        self._focus_job = self.top.after(150, self._check_focus)

    def _check_focus(self):
        self._focus_job = None
        if self.pinned:
            return  # pinned: clicking elsewhere (e.g. back into the chat) keeps it open
        try:
            inside = self.top.focus_get() is not None
        except (KeyError, tk.TclError):
            inside = False
        if not inside:
            self.hide()

    # ------------------------------------------------------------ add / settings
    def _start_add(self):
        if self._adding:
            return
        self._adding = True
        self.add_entry.delete(0, "end")
        self.add_frame.pack(fill="x", after=self.list_frame)
        self._reposition()
        self.add_entry.focus_set()

    def _commit_add(self, e=None):
        text = self.add_entry.get().strip()
        self._cancel_add()
        if text:
            self.on_add(text)  # caller re-renders via refresh()
        self.top.focus_set()
        return "break"

    def _cancel_add(self, e=None):
        if self._adding:
            self._adding = False
            self.add_frame.pack_forget()
            if self.visible:
                self._reposition()
                self.top.focus_set()
        return "break"

    def refresh(self, items, context=None):
        """Update the content in place (no animation, no focus change)."""
        items = list(items)
        if context is not None and context != self.context:
            self.context = context
        elif items == self.items and self.rows:
            return
        self.items = items
        self._build_rows()
        self._reposition()

    def _settings(self):
        self.hide()
        if self.on_settings:
            self.on_settings()
