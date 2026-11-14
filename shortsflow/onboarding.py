"""Helpers for the first-run experience (WebUI "Start here" tab, desktop GUI): plain-language progress, key saving, setup checklist."""
import os
import re
import time

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
# Dubbing (Dub tab): the same forward-only idea with its own milestones.
DUB_STEPS = [
    (r"Detected Video URL|Downloading(?! the speech model)", "📥 Getting your video ready..."),
    (r"Downloading the speech model", "📥 Downloading the speech model (first time only, a few minutes)..."),
    (r"Transcrib", "👂 Listening to the video (turning speech into text)..."),
    (r"Dubbing \d+ spoken segment", "🌍 Translating, recording the new voice and mixing it in..."),
    (r"\[Success\] Dubbed video ready", "✅ Done! Your dubbed video is ready below."),
]
# Photo reel tab
PHOTO_STEPS = [
    (r"Reel type", "🧐 Choosing the best photos and planning the reel..."),
    (r"Rendering Photo Reel using Remotion", "🎬 Building your reel (about a minute)..."),
    (r"\[Success\].*Photo Reel rendered", "✅ Done! Your reel is ready below."),
]
# Short names for the stage strip of the progress view (same order as the step lists above).
# None = a stage that exists but is not drawn (the speech model download only happens the first time).
_LABELS = {id(_STEPS): ["Get video", None, "Listen", "Find moments", "Render", "Titles", "Done"],
           id(DUB_STEPS): ["Get video", None, "Listen", "Dub", "Done"],
           id(PHOTO_STEPS): ["Plan", "Build", "Done"]}
_WARN_WORDS = ("credits", "rejected the API key", "rate limiting", "Could not reach", "found speech in only")


def friendly_step(line, steps=None):
    """(rank, message) for a pipeline log line that marks progress, or None."""
    if not line:
        return None
    if line.lstrip().startswith("[Warning]") and any(w in line for w in _WARN_WORDS):
        return (-1, "⚠️ " + line.split("]", 1)[1].strip())
    for rank, (pattern, message) in enumerate(steps or _STEPS):
        if re.search(pattern, line):
            return (rank, message)
    return None


class Progress:
    """Turns a stream of log lines into one status message that only moves forward (warnings are shown as they come).

    `display()` is the same thing as a small progress view: the stages as a strip, a bar, the detail ("Rendering 40%") and the time."""

    def __init__(self, start="📥 Getting your video ready...", steps=None):
        self.rank, self.message, self.steps = 0, start, steps
        self.labels = _LABELS.get(id(steps or _STEPS)) or []
        self.t0, self.frac, self.detail = time.time(), 0.0, ""

    def feed(self, line):
        hit = friendly_step(line, self.steps)
        if hit:
            rank, message = hit
            if rank == -1:
                self.message = message
            elif rank >= self.rank:
                if rank > self.rank:
                    self.frac, self.detail = 0.0, ""
                self.rank, self.message = rank, message
        self._detail(line or "")
        return self.message

    def _detail(self, line):
        """Sub-progress inside a stage, from the speech model's percent and the renderer's frame counts."""
        m = re.findall(r"Transcribe:\s+(\d+)%", line)
        if m:
            self.frac, self.detail = min(int(m[-1]), 100) / 100, f"Listening {m[-1]}%"
            return
        m = re.findall(r"Rendered (\d+)/(\d+)", line)
        if m and int(m[-1][1]) > 0:
            done, total = int(m[-1][0]), int(m[-1][1])
            self.frac, self.detail = min(done / total, 1.0), f"Rendering {100 * done // total}%"

    def _visible(self):
        """[(rank, label)] of the stages that are drawn."""
        return [(i, name) for i, name in enumerate(self.labels) if name]

    def fraction(self):
        """0..1 over the whole run (stage position plus the progress inside the stage)."""
        vis = self._visible()
        if len(vis) < 2:
            return 0.0
        if self.rank >= vis[-1][0]:
            return 1.0
        pos = max([k for k, (i, _) in enumerate(vis) if i <= self.rank] or [0])
        return min((pos + self.frac) / (len(vis) - 1), 0.99)

    def display(self):
        """The progress view as HTML for a Markdown box: stage strip, bar, message, detail and elapsed time."""
        secs = int(time.time() - self.t0)
        clock = f"{secs // 60}:{secs % 60:02d}"
        vis = self._visible()
        last = vis[-1][0] if vis else 0
        chips = ""
        for i, name in vis:
            nxt = next((j for j, _ in vis if j > i), None)
            state = "done" if self.rank >= last or (nxt is not None and self.rank >= nxt) else ("now" if self.rank >= i else "")
            chips += f'<span class="{state}">{name}</span>'
        bar = f'<div class="sf-bar"><div style="width:{int(self.fraction() * 100)}%"></div></div>'
        detail = f" · {self.detail}" if self.detail else ""
        return f'<div class="sf-progress"><div class="sf-stages">{chips}</div>{bar}<div class="sf-detail">{self.message}{detail} · {clock}</div></div>'


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
