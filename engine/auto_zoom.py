"""Pick the moments for the --auto_zoom punch-in effect.

The zoom is drawn by Remotion on the picture layer only (captions, hook title and brand stay put). Two kinds:
  * "punch": a quick push-in on an emphasised word (a number, a curiosity word, an audio-energy peak);
  * "push": a slow, gentle push-in across a sentence that starts after a pause or a full stop.
`choose_zoom_moments` is a pure function (words in, moments out) so it can be tested offline.
`zoom_scale_at` mirrors the envelope in remotion-video/src/autoZoom.ts; keep the two in sync.
"""
import re
import subprocess

SENTENCE_END = (".", "?", "!", "…")
PAUSE_SECONDS = 0.5          # a gap this long before a word counts as a sentence start
MIN_SPACING = 2.5            # seconds between two zooms (start to start)
MAX_PER_MINUTE = 10
PUNCH_SCALE = 1.08           # subtle by default
PUSH_SCALE = 1.05
PUNCH_RISE = 0.12            # seconds to reach the peak
PUNCH_LENGTH = 1.1
PUSH_LENGTH = 3.0
RETURN_SECONDS = 0.45        # seconds to ease back to 1.0 after a moment ends
EDGE = 0.25                  # no zoom in the first/last moments of the clip

_CURIOSITY = ("secret", "mistake", "nobody", "biggest", "worst", "truth", "never", "always", "actually",
              "crazy", "insane", "shocking", "free", "million", "billion", "stop", "wrong", "warning",
              "why", "how", "best", "only", "first", "last", "dangerous", "impossible")
_NUMBER = re.compile(r"\d")
_NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "hundred",
                 "thousand", "million", "billion", "percent", "double", "triple")


def _plain(word):
    return re.sub(r"[^\w$%]", "", str(word).lower())


def emphasis_strength(word):
    """0 when the word is not special, else 1-3 (numbers and money weigh most)."""
    w = _plain(word)
    if not w:
        return 0
    if _NUMBER.search(w) or "$" in w or "%" in w:
        return 3
    if w in _NUMBER_WORDS:
        return 2
    if w in _CURIOSITY:
        return 2
    return 0


def energy_peaks(audio_path, fps=20, factor=1.8, min_spacing=1.5):
    """Times (seconds) where the voice is clearly louder than usual. Returns [] on any failure."""
    try:
        import numpy as np
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            exe = "ffmpeg"
        raw = subprocess.run([exe, "-v", "error", "-i", audio_path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                             capture_output=True, timeout=120).stdout
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        hop = 8000 // fps
        n = len(samples) // hop
        if n < 10:
            return []
        rms = np.sqrt((samples[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
        active = rms[rms > 0.1 * rms.max()]
        if len(active) < 5:
            return []
        limit = factor * float(np.median(active))
        peaks, last = [], -1e9
        for i in range(1, n - 1):
            t = i / fps
            if rms[i] >= limit and rms[i] >= rms[i - 1] and rms[i] >= rms[i + 1] and t - last >= min_spacing:
                peaks.append(round(t, 2))
                last = t
        return peaks
    except Exception:
        return []


def _candidates(words, peaks):
    out = []
    prev_end = None
    prev_word = ""
    for i, w in enumerate(words):
        start = float(w["start"])
        gap = start - prev_end if prev_end is not None else 99.0
        starts_sentence = i == 0 or prev_word.rstrip().endswith(SENTENCE_END) or gap >= PAUSE_SECONDS
        strength = emphasis_strength(w.get("word", ""))
        near_peak = any(abs(p - start) <= 0.3 for p in peaks)
        if strength:
            out.append({"t": start, "kind": "punch", "score": strength + (1 if near_peak else 0)})
        elif near_peak:
            out.append({"t": start, "kind": "punch", "score": 1.5})
        elif starts_sentence and i > 0:
            out.append({"t": start, "kind": "push", "score": 1.0})
        prev_end = float(w.get("end", start + 0.3))
        prev_word = str(w.get("word", ""))
    return out


def choose_zoom_moments(words, duration, peaks=None, intensity=1.0, min_spacing=MIN_SPACING):
    """words: [{word,start,end}] relative to the clip. Returns [{start,end,scale,rise}] sorted, non-overlapping.

    intensity scales how far the picture zooms (0.5 = half as much, 2 = twice); 0 gives no zoom."""
    if not words or not duration or duration <= 1.0 or intensity <= 0:
        return []
    peaks = list(peaks or [])
    cap = max(1, int(duration / 60.0 * MAX_PER_MINUTE + 0.5), int(duration // 6))
    cands = [c for c in _candidates(words, peaks) if EDGE <= c["t"] <= duration - 1.0]
    # strongest first, then keep those that do not crowd an already chosen one
    chosen = []
    for c in sorted(cands, key=lambda c: (-c["score"], c["t"])):
        if len(chosen) >= cap:
            break
        if all(abs(c["t"] - k["t"]) >= min_spacing for k in chosen):
            chosen.append(c)
    chosen.sort(key=lambda c: c["t"])
    moments = []
    for idx, c in enumerate(chosen):
        nxt = chosen[idx + 1]["t"] if idx + 1 < len(chosen) else duration
        length = PUNCH_LENGTH if c["kind"] == "punch" else PUSH_LENGTH
        start = max(0.0, c["t"] - 0.05)
        end = min(start + length, nxt - 0.2, duration - 0.1)
        if end - start < 0.4:
            continue
        base = PUNCH_SCALE if c["kind"] == "punch" else PUSH_SCALE
        rise = PUNCH_RISE if c["kind"] == "punch" else round((end - start) * 0.8, 3)
        moments.append({"start": round(start, 3), "end": round(end, 3),
                        "scale": round(1.0 + (base - 1.0) * intensity, 4), "rise": rise})
    return moments


def fill_gaps(moments, duration, max_gap=7.0, intensity=1.0):
    """Add a slow push-in in the middle of every stretch longer than `max_gap` seconds that has no zoom, so a long calm patch does
    not look frozen (the director uses it). Existing moments are kept; the new ones are subtle, 2.6 s long, and stay clear of
    their neighbours and of the clip edges."""
    out = sorted((dict(m) for m in moments or []), key=lambda m: m["start"])
    if not duration or duration <= max_gap or intensity <= 0:
        return out
    marks = [0.0] + [t for m in out for t in (m["start"], m["end"])] + [float(duration)]
    added = []
    for a, b in zip(marks[0::2], marks[1::2]):            # (end of one moment, start of the next), the first from 0
        if b - a > max_gap:
            length = 2.6
            mid = (a + b) / 2.0
            start, end = mid - length / 2, mid + length / 2
            if start - a >= 0.8 and b - end >= 0.8 and EDGE <= start and end <= duration - 0.3:
                added.append({"start": round(start, 3), "end": round(end, 3),
                              "scale": round(1.0 + (PUSH_SCALE - 1.0) * intensity, 4), "rise": round(length * 0.8, 3)})
    return sorted(out + added, key=lambda m: m["start"])


def _ease_out(p):
    p = min(1.0, max(0.0, p))
    return 1.0 - (1.0 - p) ** 3


def _ease_in_out(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3.0 - 2.0 * p)


def zoom_scale_at(t, moments):
    """Picture scale at time t (seconds): the same curve as autoZoom.ts."""
    best = 1.0
    for m in moments or []:
        s, e, peak, rise = m["start"], m["end"], m["scale"], max(0.01, m.get("rise", PUNCH_RISE))
        if t < s or t > e + RETURN_SECONDS:
            continue
        if t < s + rise:
            env = _ease_out((t - s) / rise)
        elif t <= e:
            env = 1.0
        else:
            env = 1.0 - _ease_in_out((t - e) / RETURN_SECONDS)
        best = max(best, 1.0 + (peak - 1.0) * env)
    return best
