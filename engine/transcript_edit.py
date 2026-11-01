"""Transcript-based trimming: cut the video by editing its words.

Two ways to say what goes:

* ``--cut "so basically"`` (repeatable): every occurrence of that phrase is removed.
* ``--edit_transcript transcript.txt``: a text file the clipping run writes next to ``transcript.json``
  (``transcript.txt``). Delete words or whole lines from it, then re-run with ``--edit_transcript``; the
  deleted words are cut from the video. Only deletions count. Replaced or inserted words are ignored, so
  fixing a typo never cuts anything.

Both produce ``[(start, end)]`` spans in source-video seconds, which are carved out of the keep intervals the
same way filler removal does it (see ``engine.fillers.carve``).
"""
import difflib
import json
import re

PAD_START = 0.02  # seconds trimmed before the first deleted word
PAD_END = 0.06  # Whisper end timestamps run early, so the tail needs more


def norm(word):
    """Comparison form of a word: lower-case letters and digits only (so 'Hello,' == 'hello')."""
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def flatten_words(segments):
    """[{'word', 'start', 'end'}] for every timed word that has letters or digits, in order."""
    out = []
    for seg in segments or []:
        for w in seg.get("words") or []:
            if norm(w.get("word")):
                out.append({"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])})
    return out


def load_words(transcript_path):
    with open(transcript_path, "r", encoding="utf-8") as f:
        return flatten_words(json.load(f).get("segments", []))


def _spans(words, ranges):
    """Turn word index ranges [(i, j)) into padded, merged time spans."""
    from engine.fillers import merge_spans
    spans = []
    for i, j in ranges:
        if j > i:
            spans.append((max(0.0, words[i]["start"] - PAD_START), words[j - 1]["end"] + PAD_END))
    return merge_spans(spans)


def export_text(words, sentence_gap=0.7, width=14):
    """Editable transcript: one line per spoken sentence/pause, ~`width` words max. Lines are only layout;
    the diff works on the words alone, so you can delete words, parts of lines or whole lines."""
    lines, cur = [], []
    for k, w in enumerate(words):
        cur.append(w["word"])
        nxt = words[k + 1] if k + 1 < len(words) else None
        pause = nxt is not None and nxt["start"] - w["end"] >= sentence_gap
        if nxt is None or pause or len(cur) >= width or re.search(r"[.!?]$", w["word"]):
            lines.append(" ".join(cur))
            cur = []
    return "\n".join(lines) + "\n"


def spans_from_phrases(words, phrases):
    """Spans covering every occurrence of each phrase (matched on normalised words)."""
    keys = [norm(w["word"]) for w in words]
    ranges = []
    for phrase in phrases or []:
        target = [t for t in (norm(p) for p in phrase.split()) if t]
        if not target:
            continue
        n = len(target)
        i = 0
        while i <= len(keys) - n:
            if keys[i:i + n] == target:
                ranges.append((i, i + n))
                i += n
            else:
                i += 1
    return _spans(words, ranges)


def spans_from_edit(words, edited_text):
    """Spans for the words present in the original but missing from `edited_text`."""
    old = [norm(w["word"]) for w in words]
    new = [t for t in (norm(p) for p in edited_text.split()) if t]
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    ranges = [(i1, i2) for tag, i1, i2, _j1, _j2 in sm.get_opcodes() if tag == "delete"]
    return _spans(words, ranges)


def cut_spans(words, phrases=None, edited_text=None):
    """Union of the phrase cuts and the transcript-edit cuts."""
    from engine.fillers import merge_spans
    spans = []
    if phrases:
        spans += spans_from_phrases(words, phrases)
    if edited_text is not None:
        spans += spans_from_edit(words, edited_text)
    return merge_spans(spans)


# ---------------------------------------------------------------------------------------------------------------
# Applying the cuts: render an edited source video and a matching transcript, then let the normal pipeline run
# on that. Captions, highlight picking and every render path therefore see the edited video.
# ---------------------------------------------------------------------------------------------------------------

def keep_intervals(spans, total=None):
    """Complement of the cut `spans` over [0, total] (open-ended when `total` is None)."""
    end = float(total) if total is not None else 1e9
    out, pos = [], 0.0
    for s, e in sorted(spans):
        if s > pos:
            out.append((pos, s))
        pos = max(pos, e)
    if pos < end:
        out.append((pos, end))
    return [(a, b) for a, b in out if b - a > 0.02]


def _removed_before(spans, t):
    return sum(max(0.0, min(e, t) - s) for s, e in spans if s < t)


def remap_transcript(data, spans):
    """Copy of a Whisper transcript dict with the cut words dropped and every time moved onto the edited timeline."""
    def hit(w):
        mid = (float(w["start"]) + float(w["end"])) / 2
        return any(s <= mid < e for s, e in spans)

    def mv(t):
        return round(max(0.0, float(t) - _removed_before(spans, float(t))), 3)

    out = dict(data)
    segments = []
    for seg in data.get("segments", []):
        words = [dict(w, start=mv(w["start"]), end=mv(w["end"])) for w in seg.get("words") or [] if not hit(w)]
        if not words:
            continue
        seg = dict(seg, words=words, start=words[0]["start"], end=words[-1]["end"],
                   text="".join(w["word"] for w in words))
        for key in ("tokens", "ori_dict", "seek"):  # token/seek data no longer matches the words
            seg.pop(key, None)
        segments.append(seg)
    out["segments"] = segments
    out["text"] = "".join(s["text"] for s in segments)
    for key in ("ori_dict", "regroup_history", "nonspeech_sections"):
        out.pop(key, None)
    return out


def render_edited_video(source, keeps, out_path, workdir):
    """Re-encode `source` keeping only `keeps` ([(start, end)] seconds), audio and video in sync."""
    import os
    import shutil
    import subprocess
    n = len(keeps)
    parts = []
    for k, (a, b) in enumerate(keeps):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{k}]")
        parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{k}]")
    parts.append("".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    script = os.path.join(workdir, "cut.filter")
    with open(script, "w", encoding="utf-8") as f:
        f.write(";\n".join(parts))
    exe = shutil.which("ffmpeg")
    if not exe:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-y", "-i", source, "-filter_complex_script", script, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-c:a", "aac", "-b:a", "192k", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg could not render the edited video: {r.stderr[-400:]}")
    return out_path


def prepare_edited_source(source, session_dir, phrases=None, edit_path=None, keep_fillers=False):
    """
    Apply `--cut` / `--edit_transcript` to `source`. Returns the path of the edited video (the pipeline should use
    it from here on), or `source` unchanged when nothing needs cutting. Writes in `session_dir`:
    ``transcript.txt`` (editable words of the ORIGINAL video), ``transcript_original.json``, and, when cutting,
    ``edited_source.mp4`` plus a ``transcript.json`` remapped to it.
    """
    import os
    import shutil
    from engine.analysis import transcribe_video

    original = os.path.join(session_dir, "transcript_original.json")
    source_abs = os.path.abspath(source)
    cached = None
    if os.path.exists(original):
        with open(original, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("source_video_path") != source_abs:
            cached = None
    if cached is None:
        path = transcribe_video(source, session_dir, keep_fillers=keep_fillers)
        shutil.copyfile(path, original)
        with open(original, "r", encoding="utf-8") as f:
            cached = json.load(f)

    words = flatten_words(cached.get("segments", []))
    editable = os.path.join(session_dir, "transcript.txt")
    if not edit_path or os.path.abspath(edit_path) != os.path.abspath(editable):
        with open(editable, "w", encoding="utf-8") as f:  # never overwrite the file the user is editing
            f.write(export_text(words))
        print(f"[Log] Editable transcript: {editable} (delete words, then re-run with --edit_transcript)")

    edited_text = None
    if edit_path:
        with open(edit_path, "r", encoding="utf-8") as f:
            edited_text = f.read()
    spans = cut_spans(words, phrases=phrases, edited_text=edited_text)
    if not spans:
        print("[Log] Transcript edits: nothing to cut")
        if cached.get("source_video_path") == source_abs:
            shutil.copyfile(original, os.path.join(session_dir, "transcript.json"))
        return source

    removed = sum(e - s for s, e in spans)
    print(f"[Log] Transcript edits: cutting {len(spans)} span(s), {removed:.1f}s, from the video")
    out_path = os.path.join(session_dir, "edited_source.mp4")
    render_edited_video(source, keep_intervals(spans), out_path, session_dir)
    remapped = remap_transcript(cached, spans)
    remapped["source_video_path"] = os.path.abspath(out_path)
    with open(os.path.join(session_dir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(remapped, f, indent=2)
    return out_path


# ---------------------------------------------------------------------------------------------------------------
# Per-clip tightening for the Remotion path (--tighten / --remove_fillers): cut the extracted segment to its keep
# intervals and give Remotion a clip-local transcript whose word times match the shortened clip.
# ---------------------------------------------------------------------------------------------------------------

def plan_keeps(local, duration, padding=0.08, min_gap=0.25, min_len=0.25):
    """Pad each keep interval, drop slivers and merge near gaps (same rules as video_gen.tighten_clip)."""
    padded = []
    for s, e in sorted(local):
        ps, pe = max(0.0, s - padding), min(duration, e + padding)
        if pe - ps >= min_len:
            padded.append((ps, pe))
    merged = []
    for s, e in padded:
        if merged and s - merged[-1][1] <= min_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def clip_transcript(transcript_data, start, end, keeps):
    """Transcript limited to [start, end] with times relative to the clip, then moved onto the tightened timeline."""
    duration = end - start
    shifted = {"segments": []}
    for seg in transcript_data.get("segments", []):
        words = [dict(w, start=float(w["start"]) - start, end=float(w["end"]) - start)
                 for w in seg.get("words") or [] if float(w["end"]) > start and float(w["start"]) < end]
        if words:
            shifted["segments"].append(dict(seg, words=words, start=words[0]["start"], end=words[-1]["end"]))
    cut = [(a, b) for a, b in zip([0.0] + [k[1] for k in keeps], [k[0] for k in keeps] + [duration]) if b - a > 1e-6]
    return remap_transcript(shifted, cut)


def tighten_segment(task_path, hi, silence_intervals, transcript_data, out_dir, idx, padding=0.08, min_gap=0.25):
    """
    Cut segment `task_path` (source range hi['start']..hi['end']) down to the keep intervals in `silence_intervals`
    (source seconds). Returns (video_path, transcript_path, duration), or None when there is nothing worth cutting.
    """
    import os
    start, end = float(hi["start"]), float(hi["end"])
    local = [(max(s, start) - start, min(e, end) - start) for s, e in silence_intervals if min(e, end) > max(s, start)]
    keeps = plan_keeps(local, end - start, padding=padding, min_gap=min_gap)
    kept = sum(b - a for a, b in keeps)
    if not keeps or (end - start) - kept < 0.15:
        return None
    video = os.path.join(out_dir, f"seg_{idx}_tight.mp4")
    render_edited_video(task_path, keeps, video, out_dir)
    sub = os.path.join(out_dir, f"transcript_clip_{idx}.json")
    with open(sub, "w", encoding="utf-8") as f:
        json.dump(clip_transcript(transcript_data, start, end, keeps), f)
    return video, sub, kept
