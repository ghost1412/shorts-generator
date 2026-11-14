"""--join_reel: finished clips of one run are joined into one video, the clips stay untouched."""
import shutil
import subprocess

import pytest

from engine import reel_captions

ffmpeg = shutil.which("ffmpeg")


def _clip(path, color, seconds=2):
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=136x240:d={seconds}:r=30",
                    "-f", "lavfi", "-i", f"sine=frequency=440:d={seconds}", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(path)], check=True)


@pytest.mark.skipif(not (ffmpeg and shutil.which("ffprobe")), reason="needs ffmpeg and ffprobe")
def test_three_clips_become_one_reel_of_the_right_length(tmp_path):
    files = []
    for i, c in enumerate(("red", "green", "blue")):
        p = tmp_path / f"c{i}.mp4"
        _clip(p, c)
        files.append(str(p))
    out = reel_captions.join_clips(files, str(tmp_path / "reel.mp4"), transition="iris")
    assert out and reel_captions.clip_seconds(out) == pytest.approx(6 - 2 * 0.25, abs=0.3)
    assert reel_captions.clip_seconds(files[0]) == pytest.approx(2, abs=0.2)       # inputs unchanged


def test_fewer_than_two_readable_clips_make_no_reel(tmp_path):
    assert reel_captions.join_clips([str(tmp_path / "missing.mp4")], str(tmp_path / "r.mp4")) is None
