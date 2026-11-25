"""Walkthrough narration: one segment per scene (the demo times each scene to its audio)."""

VOICE = "Charon"
STYLE = ("Read this like a friendly, confident product walkthrough. Warm, clear, "
         "unhurried, with natural pauses:")

SEGMENTS = [
    ("intro", "This is Quick Replies for Windows. Your go-to replies, one shortcut away, "
              "in any app on your PC."),
    ("hotkey", "Click into any message box and press Control, Shift, Space. "
               "The reply bar pops up right next to your mouse."),
    ("name", "In Slack and Discord direct messages, the name placeholder fills in the "
             "person's first name. So 'Hi name' becomes 'Hi Priya'."),
    ("insert", "Click a reply, or press its number, and it's typed right where your cursor "
               "is. Whatever you had copied is put back afterwards."),
    ("send", "Hold Shift to insert and send in one go. The badge flips from Insert to Send, "
             "so you always know what will happen."),
    ("pin", "Pin the bar to keep it open, and send several replies in a row. "
            "You can drag it anywhere you like."),
    ("settings", "Add your own replies right from the bar, or open Settings to edit and "
                 "reorder them, change the shortcut, and start with Windows."),
    ("outro", "Everything stays on your PC. No account, no tracking, no internet. "
              "Quick Replies for Windows. Get it on the Microsoft Store."),
]
