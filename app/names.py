"""Window title -> {name} replacement. Pure functions only (unit-tested).

    name_for(process, title) -> first name for a 1:1 Slack/Discord DM,
                                "all" for channels / group DMs,
                                "there" for anything else.

The title patterns below started from the browser versions (CLAUDE.md section 5).
Every real desktop title collected with `python -m app.main --debug` must be added
to tests/test_names.py.
"""
import re

THERE = "there"
ALL = "all"

SLACK_PROCESSES = {"slack.exe"}
DISCORD_PROCESSES = {"discord.exe", "discordptb.exe", "discordcanary.exe"}

# Leading unread / mention markers: "(3) ", "(12+) ", "* ", "! ", "• ", "● ".
_MARKER = re.compile(r"^\s*(?:\(\d+\+?\)|[*!•●])\s*")
# Title segments are joined with " - ", " | ", " — " or " – ".
_SEP = re.compile(r"\s+[-|—–]\s+")
# Slack: "Priya Sharma (DM)", "general (Channel)", "design (Private channel)"
_SLACK_KIND = re.compile(r"^(?P<name>.*?)\s*\((?P<kind>[^()]*)\)\s*$")
_GROUP = re.compile(r",|\s(?:and|&)\s", re.IGNORECASE)


def strip_markers(title: str) -> str:
    t = title or ""
    while True:
        new = _MARKER.sub("", t, count=1)
        if new == t:
            return t.strip()
        t = new


def segments(title: str, app_word: str):
    """Split a title into parts and drop the app's own name ("Slack", "Discord")."""
    parts = [p.strip() for p in _SEP.split(strip_markers(title)) if p.strip()]
    return [p for p in parts if p.lower() != app_word]


def first_name(display: str) -> str:
    """'Priya Sharma' -> 'Priya', '@priya.s' -> 'Priya', 'raj_k' -> 'Raj'.

    Returns THERE if nothing name-like is left (e.g. emoji only).
    """
    d = (display or "").strip().lstrip("@").strip()
    token = re.split(r"[\s._]+", d, maxsplit=1)[0] if d else ""
    token = re.sub(r"^[^\w]+|[^\w]+$", "", token)  # trim punctuation/emoji at the edges
    if not token or not any(ch.isalpha() for ch in token):
        return THERE
    return token[0].upper() + token[1:]


def _slack(title: str) -> str:
    parts = segments(title, "slack")
    if not parts:
        return THERE
    conv = parts[0]
    if conv.startswith("#"):
        return ALL
    m = _SLACK_KIND.match(conv)
    if not m:
        return THERE  # Activity, Threads, Later, Huddle, ... (no kind marker)
    name, kind = m.group("name").strip(), m.group("kind").strip().lower()
    if "channel" in kind or "group" in kind:
        return ALL
    if kind in ("dm", "direct message", "direct messages"):
        return ALL if _GROUP.search(name) else first_name(name)
    return THERE


def _discord(title: str) -> str:
    parts = segments(title, "discord")
    if not parts:
        return THERE
    conv = parts[0]
    if conv.startswith("#"):
        return ALL
    if conv.startswith("@"):
        return ALL if _GROUP.search(conv) else first_name(conv)
    if _GROUP.search(conv) and len(parts) == 1:
        return ALL  # group DM shown as "priya, raj, sam"
    return THERE  # Friends, Nitro, server home, ...


def name_for(process: str, title: str) -> str:
    p = (process or "").lower()
    if p in SLACK_PROCESSES:
        return _slack(title)
    if p in DISCORD_PROCESSES:
        return _discord(title)
    return THERE


_APP_LABELS = {
    "slack.exe": "Slack", "discord.exe": "Discord", "discordptb.exe": "Discord",
    "discordcanary.exe": "Discord", "ms-teams.exe": "Teams",
    "teams.exe": "Teams", "outlook.exe": "Outlook", "olk.exe": "Outlook",
    "notepad.exe": "Notepad", "chrome.exe": "Chrome", "msedge.exe": "Edge",
    "firefox.exe": "Firefox", "code.exe": "VS Code", "winword.exe": "Word",
}


def app_label(process: str) -> str:
    """'slack.exe' -> 'Slack'; unknown 'foo.exe' -> 'Foo'; '' -> ''."""
    p = (process or "").strip()
    if not p:
        return ""
    known = _APP_LABELS.get(p.lower())
    if known:
        return known
    stem = p[:-4] if p.lower().endswith(".exe") else p
    return stem[:1].upper() + stem[1:]


def render(reply: str, name: str) -> str:
    return reply.replace("{name}", name)
