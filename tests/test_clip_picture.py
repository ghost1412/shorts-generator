import os
import subprocess

import pytest

from engine import clip_picture as cp


def test_track_stats_counts_faces_centring_and_jitter():
    track = [(0.5, 0.4, 0.2), (0.52, 0.4, 0.2), None, (0.9, 0.4, 0.2), (0.88, 0.4, 0.2)]
    s = cp.track_stats(track)
    assert s["face_found"] == 0.8
    assert s["centered"] == 0.5
    assert s["jitter"] == 0.02          # jumps: 0.02 and 0.02 (pairs with a None are skipped)


def test_track_stats_handles_nothing():
    assert cp.track_stats([]) == {"face_found": None, "centered": None, "jitter": None}
    assert cp.track_stats([None, None])["face_found"] == 0.0


def test_parse_silence_sums_spans_and_open_end():
    err = "silence_start: 1.0\nsilence_end: 2.5 | silence_duration: 1.5\nsilence_start: 9.0\n"
    assert cp.parse_silence(err, 10.0) == 0.25   # 1.5 s + 1.0 s open to the end
    assert cp.parse_silence("", 10.0) == 0.0
    assert cp.parse_silence(err, 0) is None


def test_silence_share_on_a_real_file(tmp_path):
    ff = cp._ffmpeg()
    out = str(tmp_path / "half_silent.mp4")
    try:
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:d=2", "-f", "lavfi",
                        "-i", "anullsrc=r=44100:cl=mono", "-f", "lavfi", "-i", "color=c=gray:s=160x284:d=4",
                        "-filter_complex", "[1]atrim=0:2[s];[0][s]concat=n=2:v=0:a=1[a]", "-map", "2:v", "-map", "[a]",
                        "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out], check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg not usable here")
    share = cp.silence_share(out)
    assert share is not None and 0.35 <= share <= 0.6
    assert cp.track_stats(cp.face_track(out))["face_found"] == 0.0     # a grey frame has no face
    assert os.path.exists(out)


def test_plain_captions_follow_the_caption_height_setting():
    from engine.video_gen import plain_caption_y
    assert plain_caption_y(1150) == 1400          # the default height goes to the lower third, off the speaker's face
    assert plain_caption_y(None) == 1400
    assert plain_caption_y(350) == 350
    assert plain_caption_y(5000) == 1700
