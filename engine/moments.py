"""Exact moments chosen by the user: "make a short from 7:00 to 7:45".

The AI picks moments from what is SAID, so a silent cutscene, a boss entrance or any scene you already know is missing from its
choices. Give the times instead and ShortsFlow cuts exactly those, then applies the usual captions, edit and effects.

Accepted, one per line or separated by commas / semicolons:

    7:00-7:45            minutes:seconds
    1:01:40-1:02:30      hours:minutes:seconds
    420-465              plain seconds
    7:00                 a single time: a short of the default length starting there
"""
import re

MAX_SHORT = 59.9
MIN_SHORT = 3.0


def parse_time(text):
    """Seconds from '7:00', '1:01:40', '420' or '7:00.5'; ValueError when it is not a time."""
    text = str(text).strip()
    if not re.fullmatch(r"\d+(:\d{1,2}){0,2}(\.\d+)?", text):
        raise ValueError(f"'{text}' is not a time (use 7:00, 1:01:40 or seconds like 420)")
    parts = [float(p) for p in text.split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def parse_moments(text, default_length=30.0, video_seconds=None):
    """[{start, end, viral_score, final_score, reason, user_moment}] for the ranges in `text`.

    Raises ValueError with a plain-language message for a line that cannot be read, a range that ends before it starts, or a time
    past the end of the video. Ranges longer than a minute are cut to a minute (a short is never longer)."""
    items = [t.strip() for t in re.split(r"[\n,;]+", text or "") if t.strip()]
    if not items:
        return []
    out = []
    for item in items:
        m = re.fullmatch(r"(.+?)\s*[-–—]\s*(.+)", item)
        if m:
            start, end = parse_time(m.group(1)), parse_time(m.group(2))
        else:
            start = parse_time(item)
            end = start + float(default_length)
        if end <= start:
            raise ValueError(f"'{item}': the end must come after the start")
        if video_seconds and start >= video_seconds:
            raise ValueError(f"'{item}': the video is only {video_seconds / 60:.0f} minutes long")
        if video_seconds:
            end = min(end, video_seconds)
        end = min(end, start + MAX_SHORT)
        if end - start < MIN_SHORT:
            raise ValueError(f"'{item}': a short needs at least {MIN_SHORT:.0f} seconds")
        out.append({"start": round(start, 2), "end": round(end, 2), "viral_score": 90, "final_score": 90,
                    "reason": "Chosen by you", "user_moment": True})
    return sorted(out, key=lambda h: h["start"])
