"""Native "Browse..." dialogs for the browser app.

A browser never tells a web page where a chosen file really is, so the app's own file picker has to copy every file into the app first
(minutes and gigabytes for a trip). When the app runs on your own PC it can instead open the normal file / folder dialog of the system
and use what you choose where it is, with no copy.

The dialog runs in its own short-lived Python process (a desktop dialog and a web server do not share a thread well) and prints the
choice as JSON. It is only offered where it can work: a desktop session with tkinter, and not in Docker or on a remote host
(set SHORTSFLOW_NO_DIALOG=1 to switch it off).
"""
import json
import os
import subprocess
import sys

VIDEO_TYPES = [("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mts"), ("All files", "*.*")]

_SCRIPT = """
import json
import sys
import tkinter as tk
from tkinter import filedialog

kind, title, types = sys.argv[1], sys.argv[2], [tuple(t) for t in json.loads(sys.argv[3])]
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
if kind == "folder":
    out = [filedialog.askdirectory(title=title, parent=root)]
elif kind == "files":
    out = list(filedialog.askopenfilenames(title=title, parent=root, filetypes=types))
else:
    out = [filedialog.askopenfilename(title=title, parent=root, filetypes=types)]
print(json.dumps([p for p in out if p]))
"""


def available(env=None, platform=None):
    """True when a native dialog can be shown to the person using the app."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if str(env.get("SHORTSFLOW_NO_DIALOG", "")).strip().lower() in ("1", "true", "yes", "on"):
        return False
    if env.get("SHORTSFLOW_DOCKER") or os.path.exists("/.dockerenv"):
        return False
    if str(env.get("SHORTSFLOW_REMOTE", "")).strip().lower() in ("1", "true", "yes", "on"):
        return False                        # other devices can open the app: a dialog would appear on the host's screen, not theirs
    if platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return False
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    return True


def pick(kind="file", title="Choose", types=None, run=None, timeout=900):
    """Open a dialog and return the chosen paths ([] when cancelled or no dialog could be shown).

    kind: "file" (one file), "files" (several) or "folder"."""
    run = run or subprocess.run
    try:
        r = run([sys.executable, "-c", _SCRIPT, kind, title, json.dumps(types or VIDEO_TYPES)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        paths = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return []
    return [str(p) for p in paths if isinstance(p, str) and p]


def append_line(current, paths):
    """`current` (a box of one path per line) with `paths` added, without duplicates; the box unchanged when nothing was chosen."""
    lines = [ln.strip() for ln in str(current or "").splitlines() if ln.strip()]
    for p in paths or []:
        if p not in lines:
            lines.append(p)
    return "\n".join(lines)
