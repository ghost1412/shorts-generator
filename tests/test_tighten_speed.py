import numpy as np
from moviepy import VideoClip

from engine.video_gen import plan_tighten, retime_transcript, tighten_clip, time_after_tighten


def test_plan_in_speed_mode_keeps_speech_and_speeds_the_gaps():
    # speech at 2-4 s and 8-10 s of a 12 s clip; no padding so the numbers are exact
    plan = plan_tighten(12.0, [(2.0, 4.0), (8.0, 10.0)], mode="speed", speed=5.0, padding=0.0)
    assert plan == [(0, 2.0, 5.0), (2.0, 4.0, 1.0), (4.0, 8.0, 5.0), (8.0, 10.0, 1.0)]    # trailing silence after 10 s is dropped
    cut = plan_tighten(12.0, [(2.0, 4.0), (8.0, 10.0)], mode="cut", padding=0.0)
    assert cut == [(2.0, 4.0, 1.0), (8.0, 10.0, 1.0)]
    assert plan_tighten(12.0, [], "speed", 5.0) is None and plan_tighten(12.0, [(1.0, 1.1)], "cut", None, padding=0.0) is None


def test_time_map_follows_the_sped_up_picture():
    plan = [(0, 2.0, 5.0), (2.0, 4.0, 1.0), (4.0, 8.0, 5.0), (8.0, 10.0, 1.0)]
    assert time_after_tighten(plan, 1.0) == 0.2                      # inside the first sped-up gap
    assert time_after_tighten(plan, 2.0) == 0.4 and abs(time_after_tighten(plan, 3.0) - 1.4) < 1e-9
    assert abs(time_after_tighten(plan, 8.0) - (0.4 + 2.0 + 0.8)) < 1e-9
    assert abs(time_after_tighten(plan, 9.5) - 4.7) < 1e-9
    assert time_after_tighten(plan, 11.0) is None                    # cut off the end
    gap_cut = [(2.0, 4.0, 1.0), (8.0, 10.0, 1.0)]
    assert time_after_tighten(gap_cut, 5.0) == 2.0                   # a dropped gap collapses to the next part


def test_captions_are_retimed_with_the_picture():
    tr = {"segments": [{"start": 2.0, "end": 4.0, "text": "hello world",
                        "words": [{"word": " hello", "start": 2.0, "end": 2.9}, {"word": " world", "start": 3.0, "end": 4.0}]},
                       {"start": 8.0, "end": 10.0, "text": "again",
                        "words": [{"word": " again", "start": 8.0, "end": 9.0}]},
                       {"start": 11.0, "end": 11.5, "text": "late", "words": [{"word": " late", "start": 11.0, "end": 11.5}]}]}
    plan = [(0, 2.0, 5.0), (2.0, 4.0, 1.0), (4.0, 8.0, 5.0), (8.0, 10.0, 1.0)]
    out, new_end = retime_transcript(tr, 0.0, 12.0, plan)
    words = [w for s in out["segments"] for w in s["words"]]
    assert [w["word"].strip() for w in words] == ["hello", "world", "again"]                # "late" was cut off the end
    assert words[0]["start"] == 0.4 and abs(words[1]["start"] - 1.4) < 1e-6 and abs(words[2]["start"] - 3.2) < 1e-6
    assert all(w["end"] > w["start"] for w in words)
    # a clip window that starts inside the source: times are counted from the window start
    out2, _ = retime_transcript(tr, 2.0, 12.0, [(0, 2.0, 1.0), (2.0, 6.0, 5.0), (6.0, 8.0, 1.0)])
    assert out2["segments"][0]["words"][0]["start"] == 0.0


def test_a_real_clip_gets_exactly_as_short_as_the_plan_says():
    clip = VideoClip(lambda t: np.zeros((8, 8, 3), dtype="uint8"), duration=12.0).with_fps(10)
    keep = [(2.0, 4.0), (8.0, 10.0)]
    plan = plan_tighten(12.0, keep, "speed", 5.0, padding=0.0)
    out = tighten_clip(clip, keep, mode="speed", speed=5.0, padding=0.0)
    assert abs(out.duration - sum((e - s) / r for s, e, r in plan)) < 0.35


def test_clip_cleanup_compares_audio_by_identity_not_by_frames():
    # `final_audio != sub.audio` makes MoviePy compare every audio frame of both clips after the render: minutes for a sped-up
    # clip (a render looked hung), seconds wasted on every other clip. The cleanup must use `is not`.
    import re
    src = open("engine/video_gen.py", encoding="utf-8").read()
    assert not re.search(r"final_audio\s*!=\s*sub\.audio", src)
    assert "final_audio is not sub.audio" in src
