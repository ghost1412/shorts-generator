"""Filler-word removal ("um", "uh", ...) for clips, built on Whisper word timestamps.

`--remove_fillers` makes transcription keep fillers (Whisper tends to drop them unless prompted), then carves
each filler out of the "keep" intervals that `--tighten` uses to cut silences.
"""
import re

FILLERS = frozenset({"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "hm", "mm", "mmm", "eh"})
WHISPER_PROMPT = "Um, uh, so, like, you know, I mean, er, hmm."  # nudges Whisper to write fillers down
MIN_KEEP = 0.12  # drop slivers shorter than this after carving


def is_filler(word):
    return re.sub(r"[^a-z]", "", (word or "").lower()) in FILLERS


def find_filler_spans(segments, pad_start=0.03, pad_end=0.10):
    """[(start, end)] of every filler word, widened so the breath around it goes too. Whisper's end
    timestamps for short words run early, hence the larger tail pad."""
    spans = []
    for seg in segments:
        for w in seg.get("words") or []:
            if is_filler(w.get("word")):
                spans.append((max(0.0, float(w["start"]) - pad_start), float(w["end"]) + pad_end))
    return merge_spans(spans)


def merge_spans(spans):
    out = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def refine_spans(spans, rms, fps, reach=0.25, floor=0.2):
    """
    Snap each span to the real sound in the audio. Whisper's timestamps for short words are often 0.1-0.2 s
    off, which leaves half an "uh" behind. `rms` is the loudness envelope at `fps` samples per second. From the
    loudest point near the span we walk outward until the sound drops below `floor` x its peak or stops
    falling (a valley between words), by at most `reach` seconds either way.
    """
    import numpy as np
    rms = np.asarray(rms, dtype=float)
    n = len(rms)
    out = []
    for s, e in spans:
        lo, hi = max(0, int(s * fps)), min(n, int(e * fps))
        if hi - lo < 3:
            out.append((s, e))
            continue
        peak = lo + int(np.argmax(rms[lo:hi]))
        level = rms[peak] * floor
        if rms[peak] <= 0:
            out.append((s, e))
            continue
        limit = int(reach * fps)
        i = peak
        while i > max(0, peak - limit) and rms[i - 1] > level and rms[i - 1] <= rms[i] * 1.05:
            i -= 1
        j = peak
        while j < min(n - 1, peak + limit) and rms[j + 1] > level and rms[j + 1] <= rms[j] * 1.05:
            j += 1
        out.append((min(s, i / fps), max(e, (j + 1) / fps)))
    return merge_spans(out)


def carve(intervals, spans, min_keep=MIN_KEEP):
    """Remove `spans` from the keep `intervals`; both are sorted [(start, end)]."""
    result = []
    for start, end in intervals:
        pieces = [(start, end)]
        for s, e in spans:
            if e <= start or s >= end:
                continue
            nxt = []
            for a, b in pieces:
                if e <= a or s >= b:
                    nxt.append((a, b))
                    continue
                if s > a:
                    nxt.append((a, s))
                if e < b:
                    nxt.append((e, b))
            pieces = nxt
        result += [(a, b) for a, b in pieces if b - a >= min_keep]
    return result


def remove_fillers(keep_intervals, segments, total_duration, rms=None, rms_fps=100):
    """Keep-intervals with fillers cut out. Starts from the whole video when no silence intervals exist.
    Pass the audio loudness envelope as `rms` to snap the cuts to the actual sound."""
    spans = find_filler_spans(segments)
    if rms is not None and len(spans):
        spans = refine_spans(spans, rms, rms_fps)
    base = keep_intervals or [(0.0, float(total_duration))]
    return carve(base, spans), len(spans)
