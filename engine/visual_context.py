"""Visual context: let the picture say what is going on, not only the person talking.

The clip picker reads the transcript, so it sees what the speaker SAYS. In a gameplay or reaction video the speaker often talks to the
viewers while the story happens on screen (a boss appears, a cutscene plays, a subtitle gives the plot). This module looks at a few
frames of each candidate moment with a local vision model (Ollama) and writes a one-sentence "what is on screen" description that the
ranking step and the title writer then use next to the transcript.

Everything is optional and fails safe: no Ollama, no vision-capable model, a slow answer, a bad frame: the candidates simply keep no
description and the run goes on as before. The model never sees more than a few small frames per candidate.
"""
import base64
import json
import os
import re
import subprocess
import urllib.request

PREFERRED = ("gemma3", "qwen2.5vl", "qwen2-vl", "qwen3-vl", "llama3.2-vision", "llava", "minicpm-v", "moondream")
FRAMES_PER_CLIP = 3
FRAME_WIDTH = 640
PROMPT = ("These are frames from one short moment of a video, in time order. {about}In one or two plain sentences, say what is happening "
          "on screen: who or what is shown, the action, the setting, and any subtitle or on-screen text you can read (quote it). "
          "Reply with the description only, no introduction. Do not guess names you cannot see or read.")


def ollama_base():
    url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/chat")
    return re.sub(r"/api/.*$", "", url).rstrip("/") or "http://localhost:11434"


def installed_models(base=None, timeout=5):
    """Names of the models Ollama has, [] when it is not running."""
    try:
        with urllib.request.urlopen(f"{base or ollama_base()}/api/tags", timeout=timeout) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []


def pick_vision_model(models=None):
    """The model to use for pictures: SHORTSFLOW_VISION_MODEL, else the first installed one from the PREFERRED families, else None."""
    chosen = (os.getenv("SHORTSFLOW_VISION_MODEL") or "").strip()
    if chosen:
        return chosen
    models = installed_models() if models is None else models
    for family in PREFERRED:
        for name in models:
            if family in name.lower():
                return name
    return None


def grab_frames(video, start, end, n=FRAMES_PER_CLIP, ffmpeg=None):
    """JPEG bytes of `n` frames spread over [start, end] (first and last 10% skipped), [] on any failure."""
    from engine.broll import _ffmpeg
    ffmpeg = ffmpeg or _ffmpeg()
    out, span = [], max(0.5, float(end) - float(start))
    for k in range(n):
        t = float(start) + span * (0.1 + 0.8 * (k + 0.5) / n)
        r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                            "-vf", f"scale={FRAME_WIDTH}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "-"],
                           capture_output=True)
        if r.returncode == 0 and len(r.stdout) > 500:
            out.append(r.stdout)
    return out


def clean_description(text):
    """Strip the chatty lead-in vision models like to add ("Here's a description of what is happening:") and extra whitespace."""
    lines = [ln.strip() for ln in str(text or "").strip().splitlines() if ln.strip()]
    while lines and re.match(r"^(here'?s|here is|sure|okay|ok)\b.*:\s*$", lines[0], re.I):
        lines.pop(0)
    return re.sub(r"\s+", " ", " ".join(lines)).strip().strip("*").strip()[:420]


def describe(frames, model, about="", base=None, timeout=300):
    """One description for these JPEG frames from the Ollama vision model, '' when it cannot be had."""
    if not frames or not model:
        return ""
    body = json.dumps({"model": model, "stream": False, "options": {"temperature": 0},
                       "messages": [{"role": "user", "content": PROMPT.format(about=(f"The video is: {about}. " if about else "")),
                                     "images": [base64.b64encode(f).decode() for f in frames]}]}).encode()
    req = urllib.request.Request(f"{base or ollama_base()}/api/chat", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return clean_description(json.load(r)["message"]["content"])
    except Exception as e:
        print(f"[Warning] Visual context: the vision model did not answer ({str(e)[:80]}).")
        return ""


def describe_candidates(video, highlights, about="", cache_path=None, model=None, grab=grab_frames, ask=describe, max_clips=10):
    """Copies of the highlights with `visual` set to what is on screen. Candidates it cannot describe stay as they were.

    Descriptions are cached in `cache_path` (json, keyed by start-end), so a continued run does not look again."""
    if not highlights:
        return highlights
    model = model or pick_vision_model()
    if not model:
        print("[Warning] Visual context needs a local vision model. Install one with `ollama pull gemma3:12b` (or set "
              "SHORTSFLOW_VISION_MODEL); continuing with the transcript only.")
        return highlights
    cache = {}
    if cache_path and os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}
    out, done = [], 0
    for i, h in enumerate(highlights):
        h = dict(h)
        key = f"{float(h['start']):.1f}-{float(h['end']):.1f}"
        text = cache.get(key, "")
        if not text and i < max_clips:
            text = ask(grab(video, h["start"], h["end"]), model, about)
        if text:
            h["visual"] = text
            cache[key] = text
            done += 1
        out.append(h)
    if cache_path and cache:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=1)
        except OSError:
            pass
    print(f"[Log] Visual context ({model}): described {done} of {len(highlights)} candidate moment(s).")
    return out


def story_line(h):
    """What to hand to the title writer / ranking for one clip: the on-screen description, '' when there is none."""
    return str(h.get("visual") or "").strip()
