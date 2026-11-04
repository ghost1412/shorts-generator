"""Pick highlights from a long video one stretch at a time.

Asking one LLM request to choose from a 60-minute transcript goes wrong with the small models many people run: it loses track of
the timeline, invents times past the end of the video and ignores whole parts. So for long videos the transcript is cut into
stretches of about ten minutes, each stretch is asked separately (with its own share of the clips), and every answer must stay
inside its own stretch. The results are then merged and ranked together as before.
"""
import math

CHUNK_AFTER = 1200.0        # videos up to 20 minutes are asked in one request, as before
CHUNK_SECONDS = 600.0       # target length of one stretch
MAX_CHUNKS = 8              # keeps the number of LLM requests (and the time) bounded
SLACK = 1.0                 # seconds an answer may stick out of its stretch (sentence edges)


def plan_chunks(total_seconds, chunk_after=CHUNK_AFTER, chunk_seconds=CHUNK_SECONDS, max_chunks=MAX_CHUNKS):
    """[(start, end), ...] stretches covering the video, or one stretch for a short video."""
    total = float(total_seconds or 0)
    if total <= chunk_after:
        return [(0.0, total)]
    n = max(2, min(max_chunks, int(math.ceil(total / chunk_seconds))))
    size = total / n
    return [(round(i * size, 2), round(total if i == n - 1 else (i + 1) * size, 2)) for i in range(n)]


def per_chunk_count(clip_count, n_chunks):
    """How many clips to ask each stretch for: a share of the pool plus one spare, never fewer than 2."""
    if n_chunks <= 1:
        return int(clip_count)
    return max(2, int(math.ceil(clip_count * 1.5 / n_chunks)))


def segments_in(segments, lo, hi):
    """Segments whose middle lies in [lo, hi)."""
    return [s for s in segments if lo <= (float(s["start"]) + float(s["end"])) / 2.0 < hi]


def clamp_to_chunk(h, lo, hi, slack=SLACK):
    """The highlight limited to the stretch [lo, hi], or None when it belongs somewhere else / is unusable."""
    try:
        start, end = float(h["start"]), float(h["end"])
    except (KeyError, TypeError, ValueError):
        return None
    if end <= start or start < lo - slack or start >= hi:
        return None
    out = dict(h)
    out["start"], out["end"] = max(lo, start), min(hi, end)
    return out if out["end"] > out["start"] else None
