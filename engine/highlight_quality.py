"""Boundary snapping for highlight clips.

The LLM (or the heuristic fallback) picks a start and an end in seconds, usually from a coarse window of the transcript, so
clips often begin in the middle of a sentence ("...and that's why") or stop before the payoff. This module moves each edge
to a sentence boundary taken from the word-timed transcript, trims a leading filler sentence ("So, um, okay."), and keeps a
short tail after the last word so the clip does not end on a hard cut.

Pure functions, no I/O: they work on the transcript dict Whisper writes (segments with `words`), and degrade to segment
level when there are no word timestamps, and to "leave the clip alone" when there is nothing usable.
"""
import re

SENTENCE_END = re.compile(r"[.!?…]+[\"')\]]*$")
# a trailing dot that does NOT end a sentence
NOT_END = {"mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "u.s.", "no."}
FILLER_WORDS = {"so", "um", "uh", "er", "erm", "hmm", "well", "okay", "ok", "like", "and", "but", "yeah", "right", "alright",
                "now", "then", "anyway", "you", "know", "basically", "actually", "i", "mean"}
PAUSE_SPLIT = 0.9          # a silence this long between two words also separates sentences (Whisper often omits punctuation)

DEFAULTS = {
    "max_shift": 6.0,      # never move an edge by more than this many seconds
    "tail": 0.4,           # seconds kept after the last word of the clip
    "min_len": 8.0,        # a snapped clip shorter than this is dropped back to the original
    "max_len": 59.9,       # shorts stay under a minute
    "leadin_max_words": 5,
}


def _words(transcript):
    """Flat [{word, start, end}] from the transcript; segment text stands in when a segment has no word timings."""
    out = []
    for seg in (transcript or {}).get("segments", []):
        words = seg.get("words") or []
        usable = [w for w in words if isinstance(w, dict) and "start" in w and "end" in w and str(w.get("word", "")).strip()]
        if usable:
            out.extend({"word": str(w["word"]).strip(), "start": float(w["start"]), "end": float(w["end"])} for w in usable)
        elif str(seg.get("text", "")).strip():
            out.append({"word": str(seg["text"]).strip(), "start": float(seg.get("start", 0)), "end": float(seg.get("end", 0)),
                        "segment": True})
    return out


def sentence_spans(transcript):
    """[(start, end, text)] sentences in order, from punctuation, long pauses and segment-level text."""
    spans, current = [], []

    def close():
        if current:
            spans.append((current[0]["start"], current[-1]["end"], " ".join(w["word"] for w in current)))
            current.clear()

    prev_end = None
    for w in _words(transcript):
        if current and prev_end is not None and w["start"] - prev_end >= PAUSE_SPLIT:
            close()
        current.append(w)
        text = w["word"].lower()
        if w.get("segment"):               # a whole segment of text: split it on its own punctuation
            parts = [p for p in re.split(r"(?<=[.!?…])\s+", w["word"]) if p.strip()]
            if len(parts) > 1:
                current.pop()
                dur = max(0.01, w["end"] - w["start"])
                total = sum(len(p) for p in parts) or 1
                t = w["start"]
                for p in parts:
                    seg_end = t + dur * len(p) / total
                    spans.append((t, seg_end, p.strip()))
                    t = seg_end
                prev_end = w["end"]
                continue
        if SENTENCE_END.search(w["word"]) and text not in NOT_END:    # "3.14" does not end with a dot, "Dr." is listed
            close()
        prev_end = w["end"]
    close()
    return spans


def _is_leadin(text, max_words):
    words = re.findall(r"[a-z']+", text.lower())
    return 0 < len(words) <= max_words and all(w in FILLER_WORDS for w in words)


def snap_clip(clip, spans, **opts):
    """A copy of `clip` ({start, end, ...}) with its edges moved to sentence boundaries; the original clip when nothing
    sensible can be done. Adds `orig_start` / `orig_end` / `snapped` to the copy."""
    o = {**DEFAULTS, **opts}
    if not spans:
        return clip
    start, end = float(clip["start"]), float(clip["end"])
    starts = [s for s, _, _ in spans]
    ends = [e for _, e, _ in spans]

    # --- start: a sentence start, as close as possible (earlier = keeps the whole sentence, later = skips the lead-in)
    new_start = start
    inside = next((i for i, (s, e, _) in enumerate(spans) if s - 0.05 <= start < e), None)
    if inside is not None and abs(starts[inside] - start) > 0.05:
        before = starts[inside]
        after = starts[inside + 1] if inside + 1 < len(spans) else None
        cands = [c for c in (before, after) if c is not None and abs(c - start) <= o["max_shift"] and c < end - o["min_len"]]
        if cands:
            new_start = min(cands, key=lambda c: abs(c - start))
    elif inside is None:
        # the start sits in a pause: begin with the sentence that follows it
        following = [c for c in starts if c > start]
        if following and following[0] - start <= o["max_shift"] and following[0] < end - o["min_len"]:
            new_start = following[0]
    # skip a filler sentence at the very start ("So, um, okay.")
    first = next((i for i, (s, _, _) in enumerate(spans) if abs(s - new_start) < 0.05), None)
    if first is not None and first + 1 < len(spans) and _is_leadin(spans[first][2], o["leadin_max_words"]):
        cand = starts[first + 1]
        if cand - new_start <= o["max_shift"] and cand < end - o["min_len"]:
            new_start = cand

    # --- end: after the sentence the clip stops in (finish the thought), else back to the last complete sentence
    new_end = end
    inside_e = next((i for i, (s, e, _) in enumerate(spans) if s < end <= e + 0.05), None)
    if inside_e is not None and abs(ends[inside_e] - end) > 0.05:
        forward = ends[inside_e]
        back = ends[inside_e - 1] if inside_e > 0 else None
        cands = [c for c in (forward, back) if c is not None and abs(c - end) <= o["max_shift"] and c > new_start + o["min_len"]]
        if cands:
            # finish the thought (the payoff usually lands at the end of the sentence the clip stops in)
            new_end = forward if forward in cands else min(cands, key=lambda c: abs(c - end))
    elif inside_e is None:
        # the end sits in a pause: snap back to the sentence that just finished
        prev = [e for e in ends if e <= end + 0.05]
        if prev and end - prev[-1] <= o["max_shift"] and prev[-1] > new_start + o["min_len"]:
            new_end = prev[-1]

    # --- a short tail so the clip does not stop dead on the last word, but never into the next sentence
    nxt = [s for s in starts if s > new_end + 0.01]
    tail_end = new_end + o["tail"]
    if nxt:
        tail_end = min(tail_end, nxt[0] - 0.05)
    new_end = max(new_end, tail_end)

    # --- keep it a short: too long -> end at the last sentence that fits; too short -> leave the clip as it was
    if new_end - new_start > o["max_len"]:
        fit = [e for e in ends if new_start + o["min_len"] < e <= new_start + o["max_len"]]
        new_end = (fit[-1] + min(o["tail"], 0.2)) if fit else new_start + o["max_len"]
    if new_end - new_start < o["min_len"] and (end - start) >= o["min_len"]:
        return clip

    out = dict(clip)
    out.update({"start": round(new_start, 2), "end": round(new_end, 2), "snapped": True,
                "orig_start": round(start, 2), "orig_end": round(end, 2)})
    return out


def snap_highlights(highlights, transcript, **opts):
    """Snap every highlight; clips never overlap their neighbours afterwards (the earlier one is shortened)."""
    spans = sentence_spans(transcript)
    if not spans:
        return highlights
    snapped = [snap_clip(h, spans, **opts) for h in highlights]
    order = sorted(range(len(snapped)), key=lambda i: float(snapped[i]["start"]))
    for a, b in zip(order, order[1:]):
        if float(snapped[a]["end"]) > float(snapped[b]["start"]):
            snapped[a] = dict(snapped[a], end=round(max(float(snapped[b]["start"]) - 0.01, float(snapped[a]["start"]) + 1.0), 2))
    return snapped
