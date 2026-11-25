"""Debug logging. Silent unless --debug; console only, never to a file."""
import sys

enabled = False


def debug(msg):
    if enabled and sys.stderr is not None:  # stderr is None under pythonw / --noconsole
        print(f"[qr] {msg}", file=sys.stderr, flush=True)
