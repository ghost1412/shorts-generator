"""Moments for game footage (`--content game`): story (cutscenes, dialogue) and action (fights, gameplay).

The normal picker builds its candidates from stretches where someone speaks, so a silent fight can never be chosen.
Here the candidates are sliding windows over the whole video, measured from the words, the sound and the picture, and
each window is labelled and scored by its own kind:

- story:  steady speech. Scored mostly by the words (the same keyword scoring as the normal picker).
- action: little speech, but loud or changing sound and a lot of movement. Scored by sound spikes and motion.
- quiet:  neither (menus, walking, loading). Never chosen.

The pure functions (`label`, `scores`, `choose`) take numbers and are tested offline; `measure` reads the video.
"""
import os

SPEECH_STORY = 0.8      # words per second at or above which a stretch counts as dialogue
ACTION_MIN = 0.35       # lowest normalised action signal for an action window
STORY_MIN = 0.25        # lowest normalised story signal for a story window
BUSY = 0.7              # motion AND sound at or above this: action, whatever the transcript says
INTRO = 0.03            # windows starting in the first 3% of a video (title montage, cold open) are skipped


# Smallest value that counts as "full strength" for each signal, so a video with no fights (or no talk) is not scaled up to
# look busy. From a 10-minute cutscene-and-boss-fight video: motion ran 5-19 (dialogue ~9, fight ~18), sound peaks 1-8.6,
# sound variation 0.4-2, keyword score 0-79. Motion is the mean frame change at 2 samples a second on 96x54 grey frames.
FLOORS = {"motion": 16.0, "peak": 7.0, "dyn": 1.2, "text": 40.0}


def _robust_max(values, floor=1e-6):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return 1.0
    p95 = vals[min(len(vals) - 1, int(0.95 * len(vals)))]
    return max(floor, p95)


def label(win):
    """'story', 'action' or 'quiet' from a window's words per second, normalised motion and sound.
    Heavy motion with loud sound is action even when the transcript has words in it (Whisper hears words in fight noise);
    dialogue is steady speech over calm pictures."""
    if win["motion_n"] >= BUSY and win["peak_n"] >= BUSY:
        return "action"
    if win["speech"] >= SPEECH_STORY:
        return "story"
    if max(win["motion_n"], win["peak_n"]) >= ACTION_MIN and (win["motion_n"] + win["peak_n"] + win["dyn_n"]) / 3 >= 0.25:
        return "action"
    return "quiet"


def scores(win):
    """(story_score, action_score), each 0..1."""
    story = 0.5 * win["text_n"] + 0.25 * win["dyn_n"] + 0.25 * win["motion_n"]
    action = 0.4 * win["peak_n"] + 0.35 * win["motion_n"] + 0.25 * win["dyn_n"]
    return round(story, 3), round(action, 3)


def normalise(windows):
    """Add the *_n fields (each signal divided by its robust maximum over the whole video)."""
    mx = {k: _robust_max([w[k] for w in windows], FLOORS[k]) for k in FLOORS}
    for w in windows:
        for k in mx:
            w[k + "_n"] = round(min(1.0, w[k] / mx[k]), 3)
    return windows


def choose(windows, clip_count, story_share=0.5, min_gap=0.0, skip_before=0.0):
    """Pick `clip_count` windows: about `story_share` of them story, the rest action, never overlapping and at least
    `min_gap` seconds apart. When one kind runs short, the other fills the gap. Returns windows in time order."""
    normalise(windows)
    for w in windows:
        w["kind"] = label(w)
        w["story_score"], w["action_score"] = scores(w)
    windows = [w for w in windows if w["start"] >= skip_before]
    story = sorted((w for w in windows if w["kind"] == "story" and w["story_score"] >= STORY_MIN),
                   key=lambda w: w["story_score"], reverse=True)
    action = sorted((w for w in windows if w["kind"] == "action" and w["action_score"] >= ACTION_MIN),
                    key=lambda w: w["action_score"], reverse=True)
    n_story = int(round(clip_count * max(0.0, min(1.0, story_share))))
    quotas = {"story": n_story, "action": clip_count - n_story}
    pools = {"story": story, "action": action}
    key = {"story": "story_score", "action": "action_score"}
    picked = []

    def free(w):
        return all(w["end"] + min_gap <= p["start"] or w["start"] >= p["end"] + min_gap for p in picked)

    def take(kind, n):
        got = 0
        for w in pools[kind]:
            if got >= n:
                break
            if w not in picked and free(w):
                picked.append(w)
                got += 1
        return got

    short = 0
    for kind in ("story", "action"):
        short += quotas[kind] - take(kind, quotas[kind])
    if short:  # a kind ran out: let the other (then either) fill the gap
        for kind in ("action", "story"):
            short -= take(kind, short)
            if short <= 0:
                break
    return sorted(picked, key=lambda w: w["start"])


def words_per_second(segments, start, end):
    """Words per second spoken inside [start, end], counting each transcript segment in proportion to its overlap."""
    total = 0.0
    for s in segments or []:
        a, b = float(s.get("start", 0)), float(s.get("end", 0))
        ov = min(end, b) - max(start, a)
        if ov > 0 and b > a:
            total += len(str(s.get("text", "")).split()) * ov / (b - a)
    return total / max(1e-6, end - start)


def text_in(segments, start, end):
    return " ".join(str(s.get("text", "")).strip() for s in segments or []
                    if min(end, float(s.get("end", 0))) - max(start, float(s.get("start", 0))) > 0).strip()


def windows_for(duration, length, hop=None):
    """[(start, end)] sliding windows of `length` seconds across a video of `duration` seconds."""
    hop = hop or length / 2.0
    out, t = [], 0.0
    while t + length <= duration + 1e-6:
        out.append((round(t, 2), round(t + length, 2)))
        t += hop
    if not out and duration > 5:
        out.append((0.0, round(duration, 2)))
    return out


# Titles for action moments when no AI text provider answers (the clip's own words are empty, so there is nothing to quote).
ACTION_HOOKS = ["No time to blink", "Things got intense", "Watch the whole fight", "This got out of hand", "Pure chaos",
                "One mistake and it's over", "Did you see that coming?", "The fight everyone clips", "It gets wild at the end"]


def to_highlight(w):
    """A clip entry in the same shape the rest of the pipeline uses."""
    score = w["story_score"] if w["kind"] == "story" else w["action_score"]
    if w["kind"] == "story":
        words = (w.get("words") or "").split()
        hook = " ".join(words[:8]).strip(" .,;:") or "Story moment"
        tone, reason = "tense", "Story moment: dialogue or cutscene"
    else:
        hook, tone, reason = "Action moment", "action_peak", "Action moment: loud, fast, little speech"
    v = int(round(40 + 55 * min(1.0, score)))
    return {"start": w["start"], "end": w["end"], "viral_score": v, "final_score": float(v), "score": float(v),
            "hook_text": hook, "tone": tone, "reason": reason, "kind": w["kind"]}


def measure(video_path, transcript_segments, output_dir, length=30.0, duration=None):
    """Windows with their words, sound and motion measured (reads the audio and the picture; a few minutes for an hour)."""
    import numpy as np
    from engine.analysis import extract_audio_mono, probe_duration, score_segment
    duration = duration or probe_duration(video_path)
    wins = [{"start": a, "end": b} for a, b in windows_for(duration, length)]

    # sound: loudness spikes (peak versus the video's usual level) and how much it changes inside the window
    import librosa
    sr = 16000
    audio, _ = librosa.load(extract_audio_mono(video_path, output_dir), sr=sr)
    hop = 512
    rms = librosa.feature.rms(y=audio, hop_length=hop)[0]
    per_sec = sr / hop
    median = float(np.median(rms)) + 1e-6

    # picture: how much the frame changes (2 samples a second, small grey frames, straight from ffmpeg)
    motion = _motion_per_second(video_path)

    for w in wins:
        a, b = int(w["start"] * per_sec), max(int(w["end"] * per_sec), int(w["start"] * per_sec) + 2)
        chunk = rms[a:b] if b <= len(rms) else rms[a:]
        if len(chunk) == 0:
            chunk = np.array([median])
        w["peak"] = float(np.percentile(chunk, 95) / median)
        w["dyn"] = float(np.std(chunk) / (np.mean(chunk) + 1e-6))
        m = motion[int(w["start"]):int(w["end"])]
        w["motion"] = float(np.mean(m)) if len(m) else 0.0
        w["speech"] = words_per_second(transcript_segments, w["start"], w["end"])
        w["words"] = text_in(transcript_segments, w["start"], w["end"])      # what is said (for the hook text)
        w["text"] = float(score_segment(w["words"], mode="shorts", start=w["start"], end=w["end"],
                                        target_duration=length)) if w["words"] else 0.0   # keyword score (a number)
    return wins


def _motion_per_second(video_path):
    """Mean absolute frame difference for each second of the video (list of floats)."""
    import subprocess
    import numpy as np
    w, h, fps = 96, 54, 2
    cmd = ["ffmpeg", "-v", "error", "-i", video_path, "-vf", f"fps={fps},scale={w}:{h},format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    data = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = len(data) // (w * h)
    if n < 2:
        return []
    frames = data[: n * w * h].reshape(n, h, w).astype(np.float32)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    diffs = np.concatenate([[0.0], diffs])
    seconds = int(np.ceil(n / fps))
    return [float(diffs[i * fps:(i + 1) * fps].mean()) for i in range(seconds)]


def pick_game_moments(video_path, transcript_path, output_dir, clip_count=3, target_duration=30.0, story_share=0.5):
    """Highlights for a game video: a mix of story and action moments. Result: list of clip dicts (time order)."""
    import json
    with open(transcript_path, "r", encoding="utf-8") as f:
        segments = json.load(f).get("segments", [])
    length = float(target_duration or 30.0)
    wins = measure(video_path, segments, output_dir, length=length)
    total = wins[-1]["end"] if wins else 0.0
    skip = INTRO * total if total > 120 else 0.0
    chosen = choose(wins, clip_count, story_share=story_share, min_gap=length, skip_before=skip)
    out = [to_highlight(w) for w in chosen]
    from engine import puzzle_variety as pv
    for h in out:
        if h["kind"] == "action":
            h["hook_text"] = pv.fresh(ACTION_HOOKS, "game_action_hook")      # not the same title twice in a row
    n_story = sum(1 for h in out if h["kind"] == "story")
    print(f"[Log] Game moments: {n_story} story + {len(out) - n_story} action of {len(wins)} windows measured.")
    return out
