"""Cold open: start a short with its strongest line, then play the clip from its beginning.

Short-form viewers decide in two seconds. A cold open puts the best sentence of the clip (usually the payoff, from the later
part) first, then rewinds to the start so the story plays in full: "teaser + clip".

It works on the FINISHED clip file, so it needs no change to the renderers. The captions, B-roll and audio clean-up are
already in the file, which means the teaser carries the right words by construction and nothing has to be re-timed inside
the render. Only things that refer to the clip's timeline afterwards (the .srt file) are shifted by the teaser length.

`pick_hook` chooses the sentence, `apply_to_clip` builds "teaser + clip" with FFmpeg and replaces the file, and `shift_cues`
moves subtitle cues. Everything fails safe: when no good line exists, or FFmpeg fails, the clip is left as it was.
"""
import os
import re
import subprocess

from engine.highlight_quality import _is_leadin, sentence_spans
from engine.topics import clip_counter, cosine

MIN_CLIP = 14.0          # shorter clips are not worth a teaser
MIN_TEASER = 1.5
MAX_TEASER = 6.0
MAX_TOTAL = 59.9         # the pipeline keeps shorts under a minute
TAIL = 0.15


def _default_score(text):
    try:
        from engine.analysis import score_segment
        return float(score_segment(text, mode="shorts"))
    except Exception:
        return 0.0


def pick_hook(words, duration, hint=None, score_fn=None, min_clip=MIN_CLIP, min_teaser=MIN_TEASER, max_teaser=MAX_TEASER):
    """{'start', 'end', 'text'} on the clip's timeline for the sentence to show first, or None.

    words: [{word, start, end}] on the finished clip's timeline. A sentence qualifies when it is not the first one, starts
    after the first quarter of the clip, lasts min_teaser..max_teaser seconds, has at least 4 words and is not filler. The
    best is the one with the highest heuristic score (shouting, numbers, curiosity words ...), a little extra for ! and ?, for
    sitting late in the clip (payoff) and for matching the clip's hook text when given."""
    if not words or duration < min_clip:
        return None
    score_fn = score_fn or _default_score
    spans = sentence_spans({"segments": [{"words": words}]})
    if len(spans) < 3:
        return None
    hint_counter = clip_counter({"segments": [{"words": [], "text": hint, "start": 0, "end": duration}]}, 0, duration) if hint else None
    best, best_score = None, 0.0
    for i, (s, e, text) in enumerate(spans):
        length = e - s
        if i == 0 or s < duration * 0.25 or not (min_teaser <= length <= max_teaser):
            continue
        if len(text.split()) < 4 or _is_leadin(text, 6):
            continue
        sc = score_fn(text)
        sc += 2.0 if text.rstrip().endswith(("!", "?")) else 0.0
        sc += 2.0 * (s / duration)                                              # later in the clip = more of a payoff
        if hint_counter:
            sc += 4.0 * cosine(clip_counter({"segments": [{"words": [], "text": text, "start": 0, "end": 1}]}, 0, 1), hint_counter)
        if sc > best_score:
            best, best_score = (s, e, text), sc
    if best is None:
        return None
    s, e, text = best
    nxt = [a for a, _, _ in spans if a > e]
    end = min(duration, e + (min(TAIL, nxt[0] - e - 0.05) if nxt else TAIL))
    return {"start": round(s, 2), "end": round(max(end, e), 2), "text": text.strip(), "score": round(best_score, 2)}


def _ffmpeg():
    from engine.broll import _ffmpeg as find
    return find()


def build_command(ffmpeg, video, hook, output, has_audio=True):
    """FFmpeg command: [teaser = hook range of the clip] + [the whole clip], re-encoded once."""
    t0, t1 = hook["start"], hook["end"]
    d = t1 - t0
    v = (f"[0:v]split=2[va][vb];[va]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS,fps=30[v0];"
         f"[vb]setpts=PTS-STARTPTS,fps=30[v1];")
    if has_audio:
        a = (f"[0:a]asplit=2[aa][ab];[aa]atrim=start={t0:.3f}:end={t1:.3f},asetpts=PTS-STARTPTS,"
             f"afade=t=in:d=0.04,afade=t=out:st={max(0.0, d - 0.08):.3f}:d=0.08[a0];[ab]asetpts=PTS-STARTPTS[a1];"
             f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
        maps = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        a = "[v0][v1]concat=n=2:v=1:a=0[v]"
        maps = ["-map", "[v]", "-an"]
    return [ffmpeg, "-y", "-i", video, "-filter_complex", v + a, *maps,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output]


def apply_to_clip(video, words, hint=None, score_fn=None):
    """Prepend the cold open to `video` in place. Returns {'start','end','duration','text'} (the teaser, on the OLD timeline),
    or None when the clip was left untouched. Never raises."""
    try:
        ffmpeg = _ffmpeg()
        from engine.broll import _probe
        _, _, duration = _probe(video, ffmpeg)
        hook = pick_hook(words, duration, hint=hint, score_fn=score_fn)
        if not hook:
            print(f"[Log] Cold open: no strong line to lead with in {os.path.basename(video)}; clip left as it was.")
            return None
        teaser = hook["end"] - hook["start"]
        if duration + teaser > MAX_TOTAL:
            print(f"[Log] Cold open: {os.path.basename(video)} would pass {MAX_TOTAL:.0f}s with the teaser; skipped.")
            return None
        banner = subprocess.run([ffmpeg, "-i", video], capture_output=True, text=True).stderr
        tmp = os.path.join(os.path.dirname(os.path.abspath(video)), f".coldopen_{os.getpid()}_{os.path.basename(video)}")
        try:
            res = subprocess.run(build_command(ffmpeg, video, hook, tmp, has_audio=bool(re.search(r"Audio:", banner))),
                                 capture_output=True, text=True)
            if res.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) < 1000:
                print(f"[Warning] Cold open failed: {res.stderr[-300:].strip()}")
                return None
            os.replace(tmp, video)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        print(f"[Log] Cold open: {os.path.basename(video)} now starts with {teaser:.1f}s: {hook['text'][:70]!r}")
        return {"start": hook["start"], "end": hook["end"], "duration": round(teaser, 2), "text": hook["text"]}
    except Exception as e:
        print(f"[Warning] Cold open skipped for {os.path.basename(str(video))}: {e}")
        return None


def _sidecar(video):
    return f"{video}.coldopen.json"


def load_applied(video):
    """The info of a cold open already built into `video` (an earlier run, --use_cache), or None. It only counts while the
    file is exactly as it was left: a fresh render has another size and is processed again."""
    import json
    try:
        with open(_sidecar(video), "r", encoding="utf-8") as f:
            data = json.load(f)
        if int(data.get("file_size", -1)) == os.path.getsize(video):
            return data["info"]
    except (OSError, ValueError, KeyError):
        pass
    return None


def save_applied(video, info):
    import json
    try:
        with open(_sidecar(video), "w", encoding="utf-8") as f:
            json.dump({"file_size": os.path.getsize(video), "info": info}, f)
    except OSError:
        pass


def shift_cues(segments, info):
    """Subtitle segments for the clip WITH its cold open: a cue for the teaser, then every original cue moved later by the
    teaser length. segments: [{start, end, text}] on the old timeline; info: the dict returned by apply_to_clip (or None)."""
    if not info:
        return list(segments)
    d = float(info["duration"])
    out = [{"start": 0.0, "end": round(d, 3), "text": info["text"]}]
    out.extend(dict(s, start=round(float(s["start"]) + d, 3), end=round(float(s["end"]) + d, 3)) for s in segments)
    return out
