"""Helpers for the first-run experience (WebUI "Start here" tab, desktop GUI): plain-language progress, key saving, setup checklist."""
import os
import re

# Ordered milestones: (regex, message). A tracker only ever moves forward through this list.
_STEPS = [
    (r"Starting AI Extraction|Downloading(?! the speech model)", "📥 Getting your video ready..."),
    (r"Downloading the speech model", "📥 Downloading the speech model (first time only, a few minutes)..."),
    (r"Transcrib", "👂 Listening to the video (turning speech into text)..."),
    (r"outline|Analyzing visual motion|Merging adjacent|Virality Scoring|rating top", "🔎 Finding the best moments..."),
    (r"Extracting \d+ segments|Queueing extraction|Tightened|Remotion", "🎬 Cutting, framing and captioning your shorts..."),
    (r"Viral thumbnail|thumbnail badge", "✍️ Writing titles and thumbnails..."),
    (r"SUCCESS! Extracted videos|Skip Upload flag detected", "✅ Done! Your shorts are ready below."),
]
_WARN_WORDS = ("credits", "rejected the API key", "rate limiting", "Could not reach")


def friendly_step(line):
    """(rank, message) for a pipeline log line that marks progress, or None."""
    if not line:
        return None
    if line.lstrip().startswith("[Warning]") and any(w in line for w in _WARN_WORDS):
        return (-1, "⚠️ " + line.split("]", 1)[1].strip())
    for rank, (pattern, message) in enumerate(_STEPS):
        if re.search(pattern, line):
            return (rank, message)
    return None


class Progress:
    """Turns a stream of log lines into one status message that only moves forward (warnings are shown as they come)."""

    def __init__(self, start="📥 Getting your video ready..."):
        self.rank, self.message = 0, start

    def feed(self, line):
        hit = friendly_step(line)
        if hit:
            rank, message = hit
            if rank == -1:
                self.message = message
            elif rank >= self.rank:
                self.rank, self.message = rank, message
        return self.message


def save_env_key(env_path, name, value):
    """Add or replace `NAME=value` in a .env file (created when missing). Returns True on success. The key is never echoed."""
    value = (value or "").strip().strip("\"'")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name or "") or not value or any(c.isspace() for c in value):
        return False
    lines = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    kept = [ln for ln in lines if not re.match(rf"\s*{re.escape(name)}\s*=", ln)]
    kept.append(f"{name}={value}")
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(kept) + "\n")
    os.environ[name] = value
    return True


def checklist_text(rows):
    """Plain-text version of the checklist for desktop dialogs."""
    return "\n".join(f"✅  {label}" if ok else f"⚠️  {label}\n      → {hint}" for label, ok, hint in rows)


def checklist_markdown(rows):
    """Markdown list from `workspace.doctor()` rows: green tick when ready, otherwise the plain fix."""
    out = []
    for label, ok, hint in rows:
        out.append(f"- ✅ {label}" if ok else f"- ⚠️ {label}  \n  &nbsp;&nbsp;&nbsp;↳ {hint}")
    return "\n".join(out)
