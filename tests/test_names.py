"""Title parsing for {name}.

REAL_* lists hold titles recorded from the actual desktop apps with
`python -m app.main --debug` (CLAUDE.md section 5). GUESSED_* are the starting
guesses from the browser versions; keep them only while they don't contradict a
real title.
"""
import unittest

from app.names import first_name, name_for, strip_markers

# (process, title, expected) recorded from real desktop apps. Add every new one here.
REAL_TITLES = [
]

GUESSED_TITLES = [
    # Slack
    ("slack.exe", "Priya Sharma (DM) - Acme - Slack", "Priya"),
    ("slack.exe", "* Priya Sharma (DM) - Acme - Slack", "Priya"),
    ("slack.exe", "(3) Priya Sharma (DM) - Acme - Slack", "Priya"),
    ("slack.exe", "! * priya.s (DM) - Acme - Slack", "Priya"),
    ("slack.exe", "general (Channel) - Acme - Slack", "all"),
    ("slack.exe", "design-team (Private channel) - Acme - Slack", "all"),
    ("slack.exe", "#general - Acme - Slack", "all"),
    ("slack.exe", "Priya, Raj, Sam (DM) - Acme - Slack", "all"),
    ("slack.exe", "Priya and Raj (DM) - Acme - Slack", "all"),
    ("slack.exe", "Activity - Acme - Slack", "there"),
    ("slack.exe", "Slack", "there"),
    # Discord
    ("Discord.exe", "@priya - Discord", "Priya"),
    ("Discord.exe", "Discord | @priya", "Priya"),
    ("Discord.exe", "(2) Discord | @raj_k", "Raj"),
    ("Discord.exe", "#general | Gaming Club - Discord", "all"),
    ("Discord.exe", "Discord | #general | Gaming Club", "all"),
    ("Discord.exe", "Discord | priya, raj, sam", "all"),
    ("Discord.exe", "Friends - Discord", "there"),
    ("Discord.exe", "Discord", "there"),
    # Not Slack / Discord
    ("notepad.exe", "Priya Sharma (DM) - Acme - Slack", "there"),
    ("chrome.exe", "@priya - Discord", "there"),
    ("", "", "there"),
]


class TestNameFor(unittest.TestCase):
    def check(self, cases):
        for process, title, expected in cases:
            with self.subTest(process=process, title=title):
                self.assertEqual(name_for(process, title), expected)

    def test_real_titles(self):
        self.check(REAL_TITLES)

    def test_guessed_titles(self):
        self.check(GUESSED_TITLES)


class TestHelpers(unittest.TestCase):
    def test_first_name(self):
        self.assertEqual(first_name("Priya Sharma"), "Priya")
        self.assertEqual(first_name("@priya.s"), "Priya")
        self.assertEqual(first_name("raj_k"), "Raj")
        self.assertEqual(first_name("  sam  "), "Sam")
        self.assertEqual(first_name("🙂"), "there")
        self.assertEqual(first_name(""), "there")

    def test_strip_markers(self):
        self.assertEqual(strip_markers("(3) * ! Priya"), "Priya")
        self.assertEqual(strip_markers("(12+) x"), "x")
        self.assertEqual(strip_markers("• general"), "general")


if __name__ == "__main__":
    unittest.main()
