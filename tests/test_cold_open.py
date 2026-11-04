import re
import subprocess

import imageio_ffmpeg
import pytest

from engine.cold_open import apply_to_clip, build_command, pick_hook, shift_cues

FF = imageio_ffmpeg.get_ffmpeg_exe()


def _words(sentences, wd=0.3, gap=0.5):
    t, out = 0.0, []
    for text in sentences:
        for w in text.split():
            out.append({"word": " " + w, "start": round(t, 2), "end": round(t + wd, 2)})
            t += wd + 0.02
        t += gap
    return out, t


SENT = ["So, um, okay.", "Here is how the whole story begins today.", "Then a second ordinary thing happens next.",
        "Another calm sentence about nothing special at all.", "And then the answer is two hundred dollars a month!",
        "That is all for the closing remark."]


def test_picks_a_strong_later_sentence_not_the_opening_or_filler():
    words, total = _words(SENT)
    score = lambda t: 10.0 if "dollars" in t else 0.0                      # noqa: E731
    hook = pick_hook(words, total, score_fn=score)
    assert hook and "dollars" in hook["text"]
    assert hook["start"] >= total * 0.25 and 1.5 <= hook["end"] - hook["start"] <= 6.5


def test_nothing_to_lead_with_means_none():
    words, total = _words(["Short one.", "Tiny two."])
    assert pick_hook(words, total) is None                                  # too few sentences / too short a clip
    assert pick_hook([], 30.0) is None
    words, total = _words(SENT)
    assert pick_hook(words, 10.0) is None                                   # below the minimum clip length


def test_the_clips_hook_text_breaks_ties():
    sents = ["First sentence sets things up properly here.", "A sentence about gardening tools and soil today.",
             "A sentence about the secret budget savings plan.", "A sentence about weather and clouds this week.",
             "Closing words nobody remembers at all today."]
    words, total = _words(sents)
    hook = pick_hook(words, total, hint="secret budget savings", score_fn=lambda t: 0.0)
    assert hook and "budget" in hook["text"]


def test_shift_cues_adds_a_teaser_cue_and_moves_the_rest():
    segs = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 2.0, "end": 4.0, "text": "b"}]
    out = shift_cues(segs, {"duration": 3.0, "text": "teaser"})
    assert out[0] == {"start": 0.0, "end": 3.0, "text": "teaser"}
    assert [(o["start"], o["end"]) for o in out[1:]] == [(3.0, 5.0), (5.0, 7.0)]
    assert shift_cues(segs, None) == segs and segs[0]["start"] == 0.0       # input untouched


def test_command_shape_with_and_without_audio():
    hook = {"start": 5.0, "end": 8.0}
    with_a = " ".join(build_command("ff", "in.mp4", hook, "out.mp4", True))
    no_a = " ".join(build_command("ff", "in.mp4", hook, "out.mp4", False))
    assert "concat=n=2:v=1:a=1" in with_a and "atrim=start=5.000:end=8.000" in with_a
    assert "a=0" in no_a and "-an" in no_a


def _dur(path):
    err = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s), err


def test_real_ffmpeg_prepends_the_teaser_and_keeps_audio(tmp_path):
    clip = tmp_path / "clip.mp4"
    r = subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=216x384:rate=30:duration=20",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=20", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(clip)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    words, total = _words(["Opening line of the clip goes here now.", "Second line keeps going on and on.",
                           "Third line is still quite ordinary overall.", "Fourth line is where it gets crazy!!!",
                           "Fifth line wraps things up nicely today.", "Sixth line is another closing remark."])
    before, _ = _dur(clip)
    info = apply_to_clip(str(clip), words, score_fn=lambda t: 10.0 if "crazy" in t else 0.0)
    assert info and "crazy" in info["text"]
    after, banner = _dur(clip)
    assert abs(after - (before + info["duration"])) < 0.5
    assert "Video:" in banner and "Audio:" in banner


def test_a_failure_leaves_the_clip_alone(tmp_path):
    bad = tmp_path / "not_a_video.mp4"
    bad.write_bytes(b"x" * 50)
    words, _ = _words(SENT)
    assert apply_to_clip(str(bad), words) is None and bad.read_bytes() == b"x" * 50


def test_applied_cold_open_is_remembered_only_while_the_file_is_unchanged(tmp_path):
    from engine.cold_open import load_applied, save_applied
    clip = tmp_path / "video_clip_1.mp4"
    clip.write_bytes(b"a" * 2000)
    assert load_applied(str(clip)) is None
    save_applied(str(clip), {"duration": 3.0, "text": "x"})
    assert load_applied(str(clip)) == {"duration": 3.0, "text": "x"}
    clip.write_bytes(b"b" * 2500)                      # a fresh render replaced the file
    assert load_applied(str(clip)) is None
