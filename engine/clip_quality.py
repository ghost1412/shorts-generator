"""Clip quality report for a finished run, without any human labels.

Reads a session folder (transcript.json + results.json) and measures what can be checked objectively, so a change that makes the picks
worse shows up as a number instead of a feeling:

* length      share of clips whose length is inside the asked range, and the median length
* boundaries  share of clips that start where a sentence starts and end where a sentence ends (a clip cut mid-sentence feels broken)
* overlap     seconds of overlap between clips (picking the same moment twice)
* spread      how many different parts of the video the clips come from (10 equal slices)
* speech      words per second inside the clip (a very low number is dead air)
* grounding   share of titles/descriptions that say nothing the clip does not (numbers and names checked against the transcript)

Optional gold moments (a file the owner writes: {"<video name>": [[start, end], ...]}) add recall and precision against moments a person
chose. Nothing here calls an LLM or the network.
"""
import json
import os
import re

BOUNDARY_SLOP = 0.6          # seconds between a clip edge and the nearest sentence edge that still counts as "at the boundary"
SENTENCE_END = re.compile(r"[.!?…]['\")\]]*\s*$")


def load_run(session_dir):
    """(transcript segments, results dict) of a session, (None, None) when either file is missing or unreadable."""
    try:
        with open(os.path.join(session_dir, "transcript.json"), "r", encoding="utf-8") as f:
            segs = [s for s in json.load(f).get("segments", []) if isinstance(s, dict) and "start" in s and "end" in s]
        with open(os.path.join(session_dir, "results.json"), "r", encoding="utf-8") as f:
            res = json.load(f)
        return segs, res
    except (OSError, ValueError):
        return None, None


def sentence_edges(segments):
    """(starts, ends): times where a sentence begins / ends. A segment start counts when the segment before it ended a sentence (or it is
    the first); a segment end counts when its text ends with sentence punctuation."""
    starts, ends = [], []
    prev_ended = True
    for s in sorted(segments, key=lambda x: x["start"]):
        text = str(s.get("text") or "")
        if prev_ended:
            starts.append(float(s["start"]))
        ended = bool(SENTENCE_END.search(text))
        if ended:
            ends.append(float(s["end"]))
        prev_ended = ended
    return starts, ends


def _near(t, edges, slop=BOUNDARY_SLOP):
    return any(abs(t - e) <= slop for e in edges)


def clip_text(segments, start, end):
    """What is said inside [start, end]."""
    return " ".join(str(s.get("text") or "").strip() for s in segments if s["end"] > start and s["start"] < end).strip()


def clip_words(segments, start, end):
    n = 0
    for s in segments:
        if s["end"] <= start or s["start"] >= end:
            continue
        words = s.get("words") or []
        n += sum(1 for w in words if isinstance(w, dict) and start <= float(w.get("start", -1)) < end) if words else len(str(s.get("text") or "").split())
    return n


def overlap_seconds(clips):
    """Total seconds that two clips share (each pair counted once)."""
    total = 0.0
    cs = sorted((float(c["start"]), float(c["end"])) for c in clips)
    for i, (a0, a1) in enumerate(cs):
        for b0, b1 in cs[i + 1:]:
            total += max(0.0, min(a1, b1) - max(a0, b0))
    return round(total, 2)


def spread_share(clips, video_seconds, slices=10):
    """Share of the clips that sit in a different tenth of the video than every other clip (1.0 = all from different parts)."""
    if not clips or not video_seconds:
        return None
    bins = {min(slices - 1, int(float(c["start"]) / video_seconds * slices)) for c in clips}
    return round(len(bins) / len(clips), 2)


def grounded_share(clips, segments, context=""):
    """Share of clips whose title and description sentences contain no number/name that the clip itself does not say
    (`context`: the user's own note about the video, which may name things the clip does not)."""
    from engine import title_variants
    from engine.social_gen import _description_lead
    if not clips:
        return None
    ok = 0
    for c in clips:
        said = clip_text(segments, float(c["start"]), float(c["end"]))
        extras = (c.get("hook"), context)
        problems = title_variants.grounding_problems(str(c.get("title") or ""), said, extras)
        problems += title_variants.grounding_problems(_description_lead(c.get("description")), said, extras, names=False, min_digits=2)
        ok += 0 if problems else 1
    return round(ok / len(clips), 2)


def _median(values):
    v = sorted(values)
    if not v:
        return None
    mid = len(v) // 2
    return round(v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2, 1)


def measure(segments, results, min_len=15.0, max_len=75.0):
    """The report (a dict of numbers) for one run. `min_len` / `max_len` are the allowed clip lengths in seconds."""
    clips = [c for c in (results or {}).get("clips", []) if "start" in c and "end" in c]
    starts, ends = sentence_edges(segments)
    video_seconds = max([float(s["end"]) for s in segments] or [0.0])
    lengths = [float(c["end"]) - float(c["start"]) for c in clips]
    in_range = [min_len <= x <= max_len for x in lengths]
    speech = []
    for c in clips:
        dur = max(0.1, float(c["end"]) - float(c["start"]))
        speech.append(clip_words(segments, float(c["start"]), float(c["end"])) / dur)
    return {
        "clips": len(clips),
        "median_length_s": _median(lengths),
        "length_in_range": round(sum(in_range) / len(in_range), 2) if clips else None,
        "starts_at_sentence": round(sum(_near(float(c["start"]), starts) for c in clips) / len(clips), 2) if clips else None,
        "ends_at_sentence": round(sum(_near(float(c["end"]), ends) for c in clips) / len(clips), 2) if clips else None,
        "overlap_s": overlap_seconds(clips),
        "spread": spread_share(clips, video_seconds),
        "median_words_per_s": _median(speech),
        "titles_grounded": grounded_share(clips, segments, str(((results or {}).get("settings") or {}).get("user_context") or "")),
    }


def overlap_with(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def gold_scores(clips, gold, min_cover=0.5):
    """Recall and precision against moments a person chose. A gold moment is found when one clip covers at least `min_cover` of it; a clip
    is right when it covers at least `min_cover` of one gold moment. Returns {"recall", "precision"} (None without clips or gold)."""
    cs = [(float(c["start"]), float(c["end"])) for c in clips]
    gs = [(float(g[0]), float(g[1])) for g in gold or []]
    if not cs or not gs:
        return {"recall": None, "precision": None}
    found = sum(any(overlap_with(c, g) / max(0.1, g[1] - g[0]) >= min_cover for c in cs) for g in gs)
    right = sum(any(overlap_with(c, g) / max(0.1, g[1] - g[0]) >= min_cover for g in gs) for c in cs)
    return {"recall": round(found / len(gs), 2), "precision": round(right / len(cs), 2)}


def video_key(results, session_dir):
    """The name a gold file uses for this run: the source video's file name, else the session folder name."""
    src = str((results or {}).get("source_video") or "")
    return os.path.basename(src.rstrip("/\\")) or os.path.basename(os.path.normpath(session_dir))


def report(session_dir, gold=None):
    """{"session", "video", metrics..., optional recall/precision} for one session folder, None when it has no readable run."""
    segs, res = load_run(session_dir)
    if segs is None:
        return None
    out = {"session": os.path.basename(os.path.normpath(session_dir)), "video": video_key(res, session_dir)}
    out.update(measure(segs, res))
    if gold:
        out.update(gold_scores(res.get("clips", []), gold.get(out["video"])))
    return out
