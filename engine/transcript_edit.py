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
    # one script per output: shorts are cut in parallel threads, and a shared "cut.filter" was overwritten mid-use
    # (ffmpeg then read two plans mixed together and 4 of 5 shorts were left untightened)
    script = os.path.join(workdir, os.path.splitext(os.path.basename(out_path))[0] + ".cut.filter")
    with open(script, "w", encoding="utf-8") as f:
        f.write(";\n".join(parts))
    exe = shutil.which("ffmpeg")
    if not exe:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    from engine.ffmpeg_compat import filter_complex_script_args
    cmd = [exe, "-y", "-i", source, *filter_complex_script_args(exe, script), "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-c:a", "aac", "-b:a", "192k", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"ffmpeg could not render the edited video: {r.stderr[-400:]}")
    return out_path


def prepare_edited_source(source, session_dir, phrases=None, edit_path=None, keep_fillers=False, language="en"):
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
        path = transcribe_video(source, session_dir, keep_fillers=keep_fillers, language=language)
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


PAUSE_MIN, PAUSE_MAX, PAUSE_MARGIN = 0.8, 4.0, 0.2


def word_pause_cuts(transcript_data, min_gap=PAUSE_MIN, max_gap=PAUSE_MAX, margin=PAUSE_MARGIN):
    """[(start, end)] source seconds to cut: pauses between two spoken words that last min_gap..max_gap seconds, minus
    `margin` on each side. Loudness-independent, so it also works when steady background noise (a fan, a station's hum, a
    room tone) keeps the pause from sounding silent. Longer gaps are left alone: they are usually music, action or a
    reaction, not a pause."""
    times = sorted((float(w["start"]), float(w["end"])) for s in (transcript_data or {}).get("segments", [])
                   for w in (s.get("words") or []) if isinstance(w, dict) and "start" in w and "end" in w)
    cuts, prev_end = [], None
    for ws, we in times:
        if prev_end is not None:
            gap = ws - prev_end
            if min_gap <= gap <= max_gap:
                cuts.append((round(prev_end + margin, 3), round(ws - margin, 3)))
        prev_end = we if prev_end is None else max(prev_end, we)
    return cuts


LOUD_PAUSE_RATIO = 0.75     # a pause as loud as this share of the speech level is a reaction (laughter, applause), not a pause


def _wav_samples(path):
    """(float samples scaled to -1..1, sample rate) of a 16-bit mono WAV, or (None, 0)."""
    import wave

    import numpy as np
    with wave.open(path, "rb") as wf:
        if wf.getsampwidth() != 2:
            return None, 0
        rate, channels = wf.getframerate(), wf.getnchannels()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def drop_loud_pauses(pauses, transcript_data, audio_path, ratio=LOUD_PAUSE_RATIO, win=0.1, min_len=0.3):
    """The QUIET parts of `pauses`: each pause is looked at in `win`-second windows and only the stretches (at least `min_len` long)
    whose level is below `ratio` of the speech level are returned, so laughter, applause or a reaction inside a long gap stays while the
    dead air around it is still cut. Returns `pauses` unchanged when the audio cannot be read."""
    if not pauses or not audio_path:
        return pauses
    try:
        import numpy as np
        data, rate = _wav_samples(audio_path)
        if data is None or rate <= 0:
            return pauses
        words = sorted((float(w["start"]), float(w["end"])) for sg in (transcript_data or {}).get("segments", [])
                       for w in (sg.get("words") or []) if isinstance(w, dict) and "start" in w and "end" in w)
        if len(words) > 300:
            words = words[::max(1, len(words) // 300)]

        def level(a, b):
            seg = data[max(0, int(a * rate)):max(0, int(b * rate))]
            return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0

        speech = [level(a, b) for a, b in words if b - a >= 0.08]
        speech = [v for v in speech if v > 0]
        if len(speech) < 10:
            return pauses
        limit = ratio * float(np.median(speech))
        out = []
        for a, b in pauses:
            quiet_from = None
            for k in range(int(round((b - a) / win))):
                ws = a + k * win
                if level(ws, ws + win) >= limit:                        # a loud window ends any quiet stretch
                    if quiet_from is not None and ws - quiet_from >= min_len:
                        out.append((round(quiet_from, 3), round(ws, 3)))
                    quiet_from = None
                elif quiet_from is None:
                    quiet_from = ws
            if quiet_from is not None and b - quiet_from >= min_len:
                out.append((round(quiet_from, 3), round(b, 3)))
        return out
    except Exception:
        return pauses


def subtract_intervals(keeps, cuts):
    """`keeps` (sorted (start, end) intervals) with every `cuts` interval removed."""
    out = []
    cuts = sorted(cuts)
    for ks, ke in sorted(keeps):
        pieces = [(ks, ke)]
        for cs, ce in cuts:
            if ce <= ks or cs >= ke:
                continue
            nxt = []
            for ps, pe in pieces:
                if ce <= ps or cs >= pe:
                    nxt.append((ps, pe))
                    continue
                if cs > ps:
                    nxt.append((ps, cs))
                if ce < pe:
                    nxt.append((ce, pe))
            pieces = nxt
        out.extend(p for p in pieces if p[1] - p[0] > 1e-3)
    return out


def protect_speech(keeps, transcript_data, pad=0.1):
    """`keeps` (loudness-based keep intervals) with every transcribed word (plus `pad` each side) added back, merged.
    Loudness alone can mark normal speech as silence when the loudest moments (applause, music, a shout) set the level:
    on a stage keynote it cut 6-17 s of speech from every clip. Words are never cut by tightening; only what lies between
    them is."""
    words = [(max(0.0, float(w["start"]) - pad), float(w["end"]) + pad)
             for s in (transcript_data or {}).get("segments", []) for w in (s.get("words") or [])
             if isinstance(w, dict) and "start" in w and "end" in w]
    merged = []
    for s, e in sorted(list(keeps or []) + words):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged
