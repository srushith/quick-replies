# Quick Replies for Windows

Press a shortcut in any app, pick a reply, and it's typed where your cursor is:
Slack, Discord, Teams, Outlook, Notepad, anything. The desktop companion to the
**Quick Replies for Slack & Discord** Chrome extension.

- **Ctrl+Shift+Space** opens a small reply bar next to your mouse
- `Hi {name}` becomes **Hi Priya** in Slack and Discord DMs
- Works with the Slack and Discord **desktop** apps: the text is pasted, so Backspace and Enter keep working
- 100% offline: no account, no telemetry, nothing leaves your PC

## Install

1. Get `QuickReplies.exe` (or [build it yourself](#build-from-source)) and put it anywhere,
   e.g. `Documents\QuickReplies`.
2. Double-click it. The first time, Windows may say **"Windows protected your PC"**:
   click **More info → Run anyway** (the app isn't code-signed yet). Some antivirus
   tools also flag apps built with PyInstaller; that's a false alarm.
3. A violet speech-bubble icon appears in the system tray (bottom-right, next to the
   clock; it may be hidden under the **^** arrow).

To start it automatically: right-click the tray icon → **Start with Windows**.

## Use it

| Do this | To |
|---|---|
| **Ctrl+Shift+Space** | Open the bar (in any app, with the cursor in a text box) |
| Click a reply, or press **1–9**, or **↑/↓** + **Enter** | Insert it |
| **Shift** + click / number / Enter | Insert **and send** (press Enter) |
| **Esc**, click elsewhere, or the shortcut again | Close the bar |
| **○ pin** (bar footer) | Keep the bar open after inserting, to send several replies |
| Drag the bar's header | Move it |

The badge on the highlighted reply shows **INSERT** or **⏎ SEND**, so you always know
whether Enter will be pressed. If you turn on "Press Enter after inserting" in Settings,
Shift does the opposite.

`{name}` becomes the person's first name in Slack/Discord direct messages, **all** in
channels and group chats, and **there** everywhere else.

## Add or change replies

- Quick: **+ add** at the bottom of the bar.
- Everything else: **⚙** in the bar, or tray icon → **Settings**. There you can edit, reorder
  (↑ ↓) and delete (✕) replies, change the shortcut, and turn on "Press Enter after
  inserting", "Keep the bar open (pin)" or "Start with Windows". Changes save automatically.

Settings live in `%APPDATA%\QuickRepliesDesktop\settings.json`, on this PC only.

## Known limits

- **Apps running as administrator** can't receive the text (Windows blocks it).
- The app pastes through the clipboard and then restores what you had copied. If you had copied an
  **image or files**, only text can be restored, so the image/files will be gone.
- Password fields and some secure boxes may refuse the paste.
- `{name}` only works in the Slack and Discord desktop apps.
- If the shortcut is already used by another app, you'll get a message and Settings opens
  so you can choose another.

To quit: right-click the tray icon → **Quit**.

## Privacy

See the full [privacy policy](PRIVACY.md). The app makes **no network connections**. It doesn't log your replies, clipboard or window
titles. (The `--debug` mode prints window titles to the console only, for development.)
It only ever simulates **Ctrl+V** and, if you ask it to, **Enter**.

## Build from source

Needs Windows 10/11 and Python 3.11+.

```powershell
git clone https://github.com/srushith/quick-replies.git
cd quick-replies
.\run.ps1 --debug        # creates .venv, installs requirements, runs with console logs
.\build.ps1              # runs the unit tests, then builds dist\QuickReplies.exe
```

Microsoft Store package (needs the Windows SDK):

```powershell
.\build-msix.ps1 -Version 1.0.0.0 -Register   # builds dist\QuickReplies.msix and installs it locally to test
.\build-msix.ps1 -Unregister                  # removes the local test install
```

The `.msix` is unsigned on purpose; the Store signs it. Bump `-Version` for every Store
update (the last number must stay 0).

Run the tests on their own with
`.\.venv\Scripts\python.exe -m unittest discover -s tests`.

Dependencies: the Python standard library (`tkinter`, `ctypes`, `winreg`) plus `pystray` and
`Pillow` for the tray icon, and `pyinstaller` for the build.

### Project layout

```
QuickReplies.pyw        launcher (used by Start with Windows and the exe build)
app/
  main.py               startup, single instance, DPI, wiring
  win32.py              all ctypes bindings
  hotkey.py             global hotkey thread
  inserter.py           focus restore, clipboard, Ctrl+V, clipboard restore
  popup.py              the reply bar
  settings_window.py    settings UI
  tray.py               tray icon
  config.py             settings.json (atomic save, defaults, corrupt-file backup)
  names.py              window title -> {name}
  startup.py            Start with Windows (HKCU Run key)
tests/                  unittest suites
packaging/              MSIX manifest + Store logo generator
build.ps1 / run.ps1     build and run helpers
build-msix.ps1          Microsoft Store package
```

## License

[Apache 2.0](LICENSE)
