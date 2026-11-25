"""Settings window: replies (edit / reorder / delete / add), hotkey picker, press-Enter toggle.

Every change is saved immediately; the bar picks it up the next time it opens.
"""
import tkinter as tk
import tkinter.font as tkfont

from app import startup, win32
from app.config import asset_path
from app.hotkey import format_hotkey, vk_name
from app.popup import (CARD, CYAN, DIM, ENTRY_BG, FG, FG_SOFT, MUTED, SEL, VIOLET,
                       _pick_font, mix, rrect)

ERROR = "#f87171"
OK = "#4ade80"
MAX_VISIBLE_ROWS = 7
_MODIFIER_KEYSYMS = {"Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R",
                     "Win_L", "Win_R", "Super_L", "Super_R", "Meta_L", "Meta_R"}


class SettingsWindow:
    def __init__(self, root, app):
        """app provides: cfg, save(), set_hotkey(text) -> (ok, msg),
        suspend_hotkey(), resume_hotkey()."""
        self.root = root
        self.app = app
        self.top = None
        self.scale = root.winfo_fpixels("1i") / 96.0
        fams = set(tkfont.families(root))
        ui = _pick_font(fams, "Segoe UI Variable Text", "Segoe UI")
        mono = _pick_font(fams, "Cascadia Mono", "Consolas")
        self.f_text = tkfont.Font(root, family=ui, size=10)
        self.f_small = tkfont.Font(root, family=ui, size=9)
        self.f_section = tkfont.Font(root, family=mono, size=8, weight="bold")
        self.f_key = tkfont.Font(root, family=mono, size=10, weight="bold")
        self.f_title = tkfont.Font(root, family=ui, size=14, weight="bold")
        self.vars = []
        self.capturing = False
        self._save_job = None

    def px(self, n):
        return int(round(n * self.scale))

    @property
    def is_open(self):
        return self.top is not None and self.top.winfo_exists()

    # ------------------------------------------------------------ open / close
    def show(self):
        if not self.is_open:
            self._build()
        self.top.deiconify()
        self.top.lift()
        self.top.update()
        win32.force_foreground(win32.root_hwnd(self.top.winfo_id()))
        self.top.focus_force()

    def close(self):
        if not self.is_open:
            return
        self._stop_capture(cancelled=True)
        self._commit_all()
        self._flush_save()
        self.top.destroy()
        self.top = None

    def refresh(self):
        """Replies changed elsewhere (e.g. '+ add' in the bar)."""
        if self.is_open:
            self._rebuild_rows()

    def refresh_options(self):
        """Toggles changed elsewhere (e.g. the bar's pin)."""
        if self.is_open:
            self.keep_var.set(self.app.cfg["keep_open"])
            self.startup_var.set(self.app.cfg["start_with_windows"])
            self.enter_var.set(self.app.cfg["press_enter"])

    # ------------------------------------------------------------ layout
    def _build(self):
        p = self.px
        top = self.top = tk.Toplevel(self.root, bg=CARD)
        top.title("Quick Replies — Settings")
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.resizable(False, False)
        try:
            self._icon = tk.PhotoImage(file=asset_path("icon128.png"))
            top.iconphoto(False, self._icon)
        except tk.TclError:
            pass
        top.withdraw()

        body = tk.Frame(top, bg=CARD, padx=p(22), pady=p(18))
        body.pack(fill="both", expand=True)
        width = p(440)

        # Title + gradient rule
        tk.Label(body, text="Settings", font=self.f_title, bg=CARD, fg=FG).pack(anchor="w")
        rule = tk.Canvas(body, bg=CARD, highlightthickness=0, height=p(2), width=width)
        rule.pack(fill="x", pady=(p(6), p(14)))
        steps = width // 3
        for k in range(steps):
            t = k / steps
            col = mix(CYAN, VIOLET, t / 0.6) if t < 0.6 else mix(VIOLET, CARD, (t - 0.6) / 0.4)
            rule.create_rectangle(k * 3, 0, k * 3 + 3, p(2), fill=col, outline="")

        # Replies
        self._section(body, "REPLIES")
        tk.Label(body, text="Use {name} for the person's first name (Slack/Discord DMs).\n"
                            "Clear a reply's text to delete it.",
                 font=self.f_small, bg=CARD, fg=MUTED, justify="left").pack(anchor="w",
                                                                          pady=(0, p(8)))
        list_wrap = tk.Frame(body, bg=CARD)
        list_wrap.pack(fill="x")
        self.list_canvas = tk.Canvas(list_wrap, bg=CARD, highlightthickness=0, width=width)
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar = tk.Scrollbar(list_wrap, orient="vertical",
                                      command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.rows_frame = tk.Frame(self.list_canvas, bg=CARD)
        self.list_canvas.create_window(0, 0, window=self.rows_frame, anchor="nw")
        self.list_canvas.bind("<Enter>", lambda e: top.bind_all("<MouseWheel>", self._wheel))
        self.list_canvas.bind("<Leave>", lambda e: top.unbind_all("<MouseWheel>"))

        add_row = tk.Frame(body, bg=CARD)
        add_row.pack(fill="x", pady=(p(8), 0))
        self.add_var = tk.StringVar()
        add_entry = self._entry(add_row, self.add_var)
        add_entry.pack(side="left", fill="x", expand=True, ipady=p(5))
        add_entry.bind("<Return>", lambda e: self._add())
        self._button(add_row, "+ Add", self._add, accent=True).pack(side="left", padx=(p(8), 0))
        self.add_entry = add_entry

        # Shortcut
        self._section(body, "SHORTCUT", pady=(p(20), p(6)))
        hk_row = tk.Frame(body, bg=CARD)
        hk_row.pack(fill="x")
        self.hk_canvas = tk.Canvas(hk_row, bg=CARD, highlightthickness=0, height=p(34),
                                   width=p(230), cursor="hand2", takefocus=1)
        self.hk_canvas.pack(side="left")
        self.hk_canvas.bind("<Button-1>", lambda e: self._start_capture())
        self.hk_canvas.bind("<KeyPress>", self._on_capture_key)
        self.hk_canvas.bind("<FocusOut>", lambda e: self._stop_capture(cancelled=True))
        tk.Label(hk_row, text="Click, then press the new keys.\nMust include Ctrl or Alt.",
                 font=self.f_small, bg=CARD, fg=MUTED, justify="left").pack(side="left",
                                                                          padx=(p(12), 0))
        self.hk_msg = tk.Label(body, text="", font=self.f_small, bg=CARD, fg=ERROR,
                               justify="left", anchor="w")
        self.hk_msg.pack(fill="x", pady=(p(4), 0))
        self._draw_hotkey()

        # Behavior
        self._section(body, "BEHAVIOR", pady=(p(14), p(6)))
        self.enter_var = tk.BooleanVar(value=self.app.cfg["press_enter"])
        tk.Checkbutton(body, text="  Press Enter after inserting (Shift flips it)",
                       variable=self.enter_var, command=self._toggle_enter, font=self.f_text,
                       bg=CARD, fg=FG, activebackground=CARD, activeforeground=FG,
                       selectcolor=ENTRY_BG, highlightthickness=0, bd=0,
                       cursor="hand2").pack(anchor="w")
        self.keep_var = tk.BooleanVar(value=self.app.cfg["keep_open"])
        tk.Checkbutton(body, text="  Keep the bar open after inserting (pin)",
                       variable=self.keep_var,
                       command=lambda: self.app.set_keep_open(self.keep_var.get()),
                       font=self.f_text, bg=CARD, fg=FG, activebackground=CARD,
                       activeforeground=FG, selectcolor=ENTRY_BG, highlightthickness=0,
                       bd=0, cursor="hand2").pack(anchor="w", pady=(self.px(4), 0))
        self.startup_var = tk.BooleanVar(value=self.app.cfg["start_with_windows"])
        if startup.packaged:
            # Store build: Windows owns this switch (Settings > Apps > Startup).
            row = tk.Frame(body, bg=CARD)
            row.pack(fill="x", pady=(p(8), 0))
            tk.Label(row, text="Start with Windows", font=self.f_text, bg=CARD,
                     fg=FG).pack(side="left")
            self._button(row, "Open Windows startup settings",
                         startup.open_startup_settings, small=True).pack(side="left",
                                                                           padx=(p(10), 0))
        else:
            tk.Checkbutton(body, text="  Start with Windows", variable=self.startup_var,
                           command=lambda: self.app.set_start_with_windows(
                               self.startup_var.get()),
                           font=self.f_text, bg=CARD, fg=FG, activebackground=CARD,
                           activeforeground=FG, selectcolor=ENTRY_BG, highlightthickness=0,
                           bd=0, cursor="hand2").pack(anchor="w", pady=(p(4), 0))

        # Footer
        foot = tk.Frame(body, bg=CARD)
        foot.pack(fill="x", pady=(p(18), 0))
        tk.Label(foot, text="Changes save automatically.", font=self.f_small, bg=CARD,
                 fg=MUTED).pack(side="left")
        self._button(foot, "Close", self.close).pack(side="right")

        top.bind("<Escape>", lambda e: None if self.capturing else self.close())
        self._rebuild_rows()
        top.update_idletasks()
        # Center on the screen with the pointer.
        cx, cy = win32.cursor_pos()
        area = win32.work_area_at(cx, cy) or (0, 0, top.winfo_screenwidth(),
                                              top.winfo_screenheight())
        w, h = top.winfo_reqwidth(), top.winfo_reqheight()
        x = area[0] + (area[2] - area[0] - w) // 2
        y = area[1] + max((area[3] - area[1] - h) // 3, 0)
        top.geometry(f"+{x}+{y}")
        top.deiconify()
        top.update()
        win32.dark_titlebar(win32.root_hwnd(top.winfo_id()))

    def _section(self, parent, text, pady=None):
        tk.Label(parent, text=text, font=self.f_section, bg=CARD, fg=CYAN).pack(
            anchor="w", pady=pady or (0, self.px(4)))

    def _entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, font=self.f_text, bg=ENTRY_BG, fg=FG,
                        insertbackground=CYAN, relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=DIM, highlightcolor=CYAN,
                        selectbackground=SEL, selectforeground=FG)

    def _button(self, parent, text, cmd, accent=False, small=False):
        fg = CYAN if accent else FG_SOFT
        b = tk.Label(parent, text=text, font=self.f_small if small else self.f_text,
                     bg=CARD if small else SEL, fg=fg, cursor="hand2",
                     padx=self.px(6 if small else 12), pady=self.px(2 if small else 5))
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(fg=FG, bg=mix(SEL, CYAN, 0.18)))
        b.bind("<Leave>", lambda e: b.configure(fg=fg, bg=CARD if small else SEL))
        return b

    # ------------------------------------------------------------ replies
    def _rebuild_rows(self):
        p = self.px
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self.vars = []
        replies = self.app.cfg["replies"]
        if not replies:
            tk.Label(self.rows_frame, text="No replies yet. Add one below.", font=self.f_text,
                     bg=CARD, fg=MUTED).pack(anchor="w", pady=p(6))
        for i, text in enumerate(replies):
            row = tk.Frame(self.rows_frame, bg=CARD)
            row.pack(fill="x", pady=(0, p(6)))
            tk.Label(row, text=str(i + 1) if i < 9 else "·", font=self.f_section, bg=CARD,
                     fg=MUTED, width=2).pack(side="left")
            var = tk.StringVar(value=text)
            var.trace_add("write", lambda *a, i=i, v=var: self._edited(i, v))
            e = self._entry(row, var)
            e.pack(side="left", fill="x", expand=True, ipady=p(5), padx=(p(4), p(6)))
            e.bind("<Return>", lambda ev: self.top.focus_set())
            e.bind("<FocusOut>", lambda ev: self._drop_blank())
            self.vars.append(var)
            self._button(row, "↑", lambda i=i: self._move(i, -1), small=True).pack(side="left")
            self._button(row, "↓", lambda i=i: self._move(i, 1), small=True).pack(side="left")
            self._button(row, "✕", lambda i=i: self._delete(i), small=True).pack(side="left")
        self.rows_frame.update_idletasks()
        row_h = p(40)
        height = (self.rows_frame.winfo_reqheight() if len(replies) <= MAX_VISIBLE_ROWS
                  else MAX_VISIBLE_ROWS * row_h)
        self.list_canvas.configure(height=height,
                                   scrollregion=(0, 0, self.rows_frame.winfo_reqwidth(),
                                                 self.rows_frame.winfo_reqheight()))
        self.list_canvas.itemconfigure(1, width=self.list_canvas.winfo_reqwidth())
        if len(replies) > MAX_VISIBLE_ROWS:
            self.scrollbar.pack(side="right", fill="y")
        else:
            self.scrollbar.pack_forget()
            self.list_canvas.yview_moveto(0)

    def _wheel(self, e):
        if len(self.app.cfg["replies"]) > MAX_VISIBLE_ROWS:
            self.list_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _edited(self, i, var):
        replies = self.app.cfg["replies"]
        if i < len(replies):
            replies[i] = var.get()
            self._schedule_save()

    def _commit_all(self):
        """Copy every row's text into cfg, then drop blank replies."""
        replies = self.app.cfg["replies"]
        for i, var in enumerate(self.vars):
            if i < len(replies):
                replies[i] = var.get()
        self.app.cfg["replies"] = [r for r in replies if r.strip()]

    def _drop_blank(self):
        if self.is_open and any(not r.strip() for r in self.app.cfg["replies"]):
            self._commit_all()
            self._save_now()
            self.top.after_idle(self._rebuild_rows)

    def _move(self, i, d):
        self._commit_all()
        replies = self.app.cfg["replies"]
        j = i + d
        if 0 <= i < len(replies) and 0 <= j < len(replies):
            replies[i], replies[j] = replies[j], replies[i]
        self._save_now()
        self._rebuild_rows()

    def _delete(self, i):
        self._commit_all()
        replies = self.app.cfg["replies"]
        if 0 <= i < len(replies):
            del replies[i]
        self._save_now()
        self._rebuild_rows()

    def _add(self):
        text = self.add_var.get()
        if not text.strip():
            return
        self._commit_all()
        self.app.cfg["replies"].append(text)
        self.add_var.set("")
        self._save_now()
        self._rebuild_rows()
        self.list_canvas.yview_moveto(1.0)
        self.add_entry.focus_set()

    # ------------------------------------------------------------ saving
    def _schedule_save(self):
        if self._save_job:
            self.top.after_cancel(self._save_job)
        self._save_job = self.top.after(400, self._save_now)

    def _flush_save(self):
        if self._save_job:
            self._save_now()

    def _save_now(self):
        if self._save_job and self.is_open:
            self.top.after_cancel(self._save_job)
        self._save_job = None
        self.app.save()

    def _toggle_enter(self):
        self.app.cfg["press_enter"] = bool(self.enter_var.get())
        self._save_now()

    # ------------------------------------------------------------ hotkey picker
    def _draw_hotkey(self, text=None, active=False):
        c = self.hk_canvas
        c.delete("all")
        w, h = int(c.cget("width")), int(c.cget("height"))
        rrect(c, 1, 1, w - 1, h - 1, self.px(8), fill=mix(CARD, CYAN, 0.08) if active else
              ENTRY_BG, outline=CYAN if active else DIM)
        c.create_text(w / 2, h / 2, text=text or self.app.cfg["hotkey"],
                      font=self.f_key if not active else self.f_small,
                      fill=CYAN if not active else FG)

    def _start_capture(self):
        if self.capturing:
            return
        self.capturing = True
        self.app.suspend_hotkey()  # otherwise pressing the current hotkey never reaches us
        self.hk_msg.configure(text="")
        self._draw_hotkey("Press new shortcut… (Esc cancels)", active=True)
        self.hk_canvas.focus_set()

    def _stop_capture(self, cancelled):
        if not self.capturing:
            return
        self.capturing = False
        if cancelled:
            self.app.resume_hotkey()
        if self.is_open:
            self._draw_hotkey()

    def _on_capture_key(self, e):
        if not self.capturing:
            return
        if e.keysym == "Escape":
            self._stop_capture(cancelled=True)
            return "break"
        if e.keysym in _MODIFIER_KEYSYMS:
            return "break"
        mods = 0
        if win32.is_down(win32.VK_CONTROL):
            mods |= win32.MOD_CONTROL
        if win32.is_down(win32.VK_MENU):
            mods |= win32.MOD_ALT
        if win32.is_down(win32.VK_SHIFT):
            mods |= win32.MOD_SHIFT
        win = win32.is_down(win32.VK_LWIN) or win32.is_down(win32.VK_RWIN)
        error = None
        if win:
            error = "Shortcuts with the Windows key aren't supported."
        elif not mods & (win32.MOD_CONTROL | win32.MOD_ALT):
            error = "Include Ctrl or Alt."
        elif vk_name(e.keycode) is None:
            error = "That key can't be used. Try a letter, number, Space or F-key."
        elif mods == win32.MOD_ALT and e.keycode == win32.VK_SPACE:
            error = "Alt+Space opens the Windows window menu. Pick another."
        if error:
            self.hk_msg.configure(text=error, fg=ERROR)
            return "break"
        text = format_hotkey(mods, e.keycode)
        self.capturing = False
        ok, msg = self.app.set_hotkey(text)
        self.hk_msg.configure(text=msg, fg=OK if ok else ERROR)
        self._draw_hotkey()
        self.top.focus_set()
        return "break"
