"""Clip quality report for a finished run, without any human labels.

Reads a session folder (transcript.json + results.json) and measures what can be checked objectively, so a change that makes the picks
worse shows up as a number instead of a feeling:

* length      share of clips whose length is inside the asked range, and the median length
* boundaries  share of clips that start where a sentence starts and end where a sentence ends (a clip cut mid-sentence feels broken)
* overlap     seconds of overlap between clips (picking the same moment twice)
* spread      how many different parts of the video the clips come from (10 equal slices)
* hook        share of clips that open on a line that stands alone (no filler or connective first, no long silent lead-in, 4+ words)
* speech      words per second inside the clip (a very low number is dead air)
* grounding   share of titles/descriptions that say nothing the clip does not (numbers and names checked against the transcript)

Optional gold moments (a file the owner writes: {"<video name>": [[start, end], ...]}) add recall and precision against moments a person
chose. Nothing here calls an LLM or the network.
"""
import json
import os
import re

BOUNDARY_SLOP = 0.6          # seconds between a clip edge and the nearest sentence edge that still counts as "at the boundary"


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
    """(starts, ends): times where a sentence begins / ends, found the same way the clip snapper finds them (engine.highlight_quality):
    word-level punctuation, and a pause of 0.9 s or more also separates sentences. Falls back to segment text without word times."""
    from engine.highlight_quality import sentence_spans
    spans = sentence_spans({"segments": list(segments)})
    return [float(s[0]) for s in spans], [float(s[1]) for s in spans]


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
        title = str(c.get("title") or "")
        if title.startswith("Clip #") and title[6:].isdigit():
            title = ""     # the placeholder of a highlights reel clip (the reel has one title): it claims nothing
        problems = title_variants.grounding_problems(title, said, extras)
        problems += title_variants.grounding_problems(_description_lead(c.get("description")), said, extras, names=False, min_digits=2)
        ok += 0 if problems else 1
    return round(ok / len(clips), 2)


def _median(values):
    v = sorted(values)
    if not v:
        return None
    mid = len(v) // 2
    return round(v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2, 1)


def length_vs_target(lengths, target, tolerance=0.25):
    """Share of clips within +-`tolerance` of the asked length. Independent of the sentence rules the snapper uses, so a change that
    shortens clips (for a better opening, say) shows up here. None without a target or for a highlights reel (one video)."""
    try:
        target = float(target or 0)
    except (TypeError, ValueError):
        return None
    if target <= 0 or not lengths:
        return None
    return round(sum(abs(x - target) <= tolerance * target for x in lengths) / len(lengths), 2)


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
        "length_vs_target": length_vs_target(lengths, ((results or {}).get("settings") or {}).get("target_duration")),
        "starts_at_sentence": round(sum(_near(float(c["start"]), starts) for c in clips) / len(clips), 2) if clips else None,
        "ends_at_sentence": round(sum(_near(float(c["end"]), ends) for c in clips) / len(clips), 2) if clips else None,
        "overlap_s": overlap_seconds(clips),
        "spread": spread_share(clips, video_seconds),
        "median_words_per_s": _median(speech),
        "titles_grounded": grounded_share(clips, segments, str(((results or {}).get("settings") or {}).get("user_context") or "")),
        "hook_ok": round(sum(hook_ok(segments, float(c["start"]), float(c["end"])) for c in clips) / len(clips), 2) if clips else None,
        "hook_cue": round(sum(hook_cue(segments, float(c["start"]), float(c["end"])) for c in clips) / len(clips), 2) if clips else None,
        "self_contained": round(sum(self_contained_opening(segments, float(c["start"]), float(c["end"])) for c in clips) / len(clips), 2) if clips else None,
        "clean_end": round(sum(clean_ending(segments, float(c["start"]), float(c["end"])) for c in clips) / len(clips), 2) if clips else None,
        "gaps_s": _median([speech_gaps(segments, float(c["start"]), float(c["end"])) for c in clips]),
    }


def _file_seconds(path):
    """Length of a video file from ffprobe/ffmpeg, None when it cannot be read."""
    import re
    import subprocess
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    try:
        r = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def cut_seconds(results, session_dir):
    """Median seconds that tightening removed per clip: the picked span minus the finished file's length (clips with a
    cold open are skipped: it adds seconds). None when the clip files are not there."""
    cut = []
    for c in (results or {}).get("clips", []):
        if c.get("cold_open") or "start" not in c:
            continue
        files = clip_videos({"clips": [c]}, session_dir)
        secs = _file_seconds(files[0]) if files else None
        if secs is not None:
            cut.append(max(0.0, float(c["end"]) - float(c["start"]) - secs))
    return _median(cut)


GAP_MIN = 0.6      # a pause between two words this long counts as dead air (the same length the picture check uses)


def speech_gaps(segments, start, end, gap_min=GAP_MIN):
    """Seconds of pauses (>= gap_min) between the timed words spoken inside [start, end], plus a silent lead-in and tail.
    Loudness-independent: quiet speech still has word timings. Compare with cut_s (what tightening removed)."""
    times = sorted((float(w["start"]), float(w["end"])) for s in segments for w in (s.get("words") or [])
                   if isinstance(w, dict) and "start" in w and "end" in w and start <= float(w["start"]) < end)
    if not times:
        return round(end - start, 2)
    total, prev = 0.0, start
    for ws, we in times:
        if ws - prev >= gap_min:
            total += ws - prev
        prev = max(prev, we)
    if end - prev >= gap_min:
        total += end - prev
    return round(total, 2)


from engine.highlight_quality import weak_opening  # noqa: E402
HOOK_LEAD_S = 1.5      # the first word must come this soon after the clip start
HOOK_MIN_WORDS = 4     # the first sentence needs this many words to stand alone
HOOK_MIN_QUESTION_WORDS = 2     # a question needs fewer


def hook_ok(segments, start, end):
    """True when the clip opens on a line that stands alone: a word within HOOK_LEAD_S of the start, a first word that is not a filler or
    a connective ("and", "so", "uh" ...), and a first sentence of at least HOOK_MIN_WORDS words. It does not judge how catchy it is."""
    words = sorted((float(w["start"]), str(w.get("word") or w.get("text") or "").strip())
                   for s in segments for w in (s.get("words") or [])
                   if isinstance(w, dict) and "start" in w and start - 0.05 <= float(w["start"]) < end)
    if not words:        # no word times: judge the segment text
        text = clip_text(segments, start, end)
        return bool(text.split()) and not weak_opening(text) and len(text.split()) >= HOOK_MIN_WORDS
    if words[0][0] - start > HOOK_LEAD_S:
        return False
    if weak_opening(" ".join(w for _, w in words[:6])):
        return False
    n, question = 0, False
    for _, w in words:
        n += 1
        if w.endswith((".", "?", "!")):
            question = w.endswith("?")
            break
    return n >= (HOOK_MIN_QUESTION_WORDS if question else HOOK_MIN_WORDS)     # a short question ("Why does it float?") is a hook


from engine.highlight_quality import OPENING_CUES  # noqa: E402
DANGLING_PRONOUNS = {"it", "they", "he", "she", "them", "these", "those", "it's", "he's", "she's", "they're", "they've", "it'll"}


def _clip_words(segments, start, end):
    """[(start_time, text)] of the timed words inside [start, end], in order."""
    return sorted((float(w["start"]), str(w.get("word") or w.get("text") or "").strip())
                  for s in segments for w in (s.get("words") or [])
                  if isinstance(w, dict) and "start" in w and start - 0.05 <= float(w["start"]) < end)


def hook_cue(segments, start, end, window=3.0):
    """True when the first `window` seconds hold a reason to keep watching: a question, a number, or a word that speaks to the viewer or
    promises something (you, never, why, how, mistake, secret ...). Cheap text cue, not a judgement of how catchy the line is."""
    words = [(t, w) for t, w in _clip_words(segments, start, end) if t < start + window]
    if not words:
        text = clip_text(segments, start, min(end, start + window))
        words = [(0.0, w) for w in text.split()]
    return any(w.endswith("?") or any(ch.isdigit() for ch in w) or w.lower().strip(",.!?\"'") in OPENING_CUES for _, w in words)


def self_contained_opening(segments, start, end):
    """False when the first word is a pronoun or demonstrative that points at something said before the clip ("It was ...", "They said
    ...", "This is why ..."): the viewer cannot tell what it refers to. A cheap check on the first word only."""
    words = _clip_words(segments, start, end)
    first = words[0][1] if words else (clip_text(segments, start, end).split() or [""])[0]
    return first.lower().replace("\u2019", "'").strip(",.!?\"'") not in DANGLING_PRONOUNS


def clean_ending(segments, start, end):
    """False when the clip stops on a word that needs a continuation ("... places that", "... data about"): the speaker was cut off."""
    from engine.highlight_quality import trails_off_end
    words = _clip_words(segments, start, end)
    text = " ".join(w for _, w in words) if words else clip_text(segments, start, end)
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x]
    return not sentences or not trails_off_end(sentences[-1])


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


def clip_videos(results, session_dir):
    """Existing clip video files of a run (results.json stores them relative to wherever the run started)."""
    found = []
    for c in (results or {}).get("clips", []):
        p = str(c.get("video_path") or "")
        if not p:
            continue
        # The session folder first, so a run started elsewhere never picks up a same-named clip of another run.
        if os.path.isabs(p):
            cands = (p,)
        else:
            cands = (os.path.join(session_dir, p), os.path.join(session_dir, os.path.basename(p.replace("\\", "/"))), p)
        for cand in cands:
            if os.path.isfile(cand):
                found.append(cand)
                break
    return found


def report(session_dir, gold=None, picture=False):
    """{"session", "video", metrics..., optional recall/precision} for one session folder, None when it has no readable run.
    picture=True also opens the clip videos (engine.clip_picture: faces, crop jitter, silence)."""
    segs, res = load_run(session_dir)
    if segs is None:
        return None
    out = {"session": os.path.basename(os.path.normpath(session_dir)), "video": video_key(res, session_dir)}
    settings = (res or {}).get("settings") or {}
    reel = settings.get("extract_mode") == "long"
    # a highlights video's moments may be longer than a short; its "clips" are the moments of ONE file
    out.update(measure(segs, res, min_len=8.0, max_len=180.0) if reel else measure(segs, res))
    if reel:
        out.pop("length_vs_target", None)       # the target is the reel's length, not each moment's
    if gold:
        out.update(gold_scores(res.get("clips", []), gold.get(out["video"])))
    if reel:
        clips = [c for c in res.get("clips", []) if "start" in c and "end" in c]
        out["reel_s"] = round(sum(float(c["end"]) - float(c["start"]) for c in clips), 1)
        if settings.get("target_duration"):
            out["target_s"] = float(settings["target_duration"])
        files = clip_videos({"clips": clips[:1]}, session_dir)
        secs = _file_seconds(files[0]) if files else None
        if secs is not None:
            out["reel_file_s"] = round(secs, 1)
    else:
        cut = cut_seconds(res, session_dir)
        if cut is not None:
            out["cut_s"] = cut
    if picture:
        from engine import clip_picture
        out.update(clip_picture.measure_videos(clip_videos(res, session_dir)))
    return out
