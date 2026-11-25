"""Launcher: works from any working directory (Start with Windows, double-click, PyInstaller).

`python -m app.main` only works when the current directory is the project root, which
is not the case for a Run-key entry at sign-in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import main  # noqa: E402

sys.exit(main())
