"""The 9:16 crop must work for every source shape (a 1080x2400 phone video used to make FFmpeg fail)."""
import re
import subprocess

import imageio_ffmpeg
import pytest

from engine.video_gen import CENTER_CROP_9X16, generate_ffmpeg_crop_filter

FF = imageio_ffmpeg.get_ffmpeg_exe()


def _size_after(vf, src_w, src_h, tmp_path):
    out = tmp_path / "o.mp4"
    r = subprocess.run([FF, "-y", "-f", "lavfi", "-i", f"testsrc2=size={src_w}x{src_h}:rate=10:duration=1",
                        "-vf", f"{vf},scale=108:192,format=yuv420p", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]
    err = subprocess.run([FF, "-i", str(out)], capture_output=True, text=True).stderr
    return tuple(map(int, re.search(r", (\d{2,5})x(\d{2,5})[ ,]", err[err.index("Video:"):]).groups()))


@pytest.mark.parametrize("w,h", [(480, 270), (108, 240), (160, 200), (108, 192), (320, 320)])
def test_center_crop_gives_9_16_for_any_source(w, h, tmp_path):
    assert _size_after(CENTER_CROP_9X16, w, h, tmp_path) == (108, 192)


@pytest.mark.parametrize("w,h", [(640, 360), (108, 240)])
def test_tracked_crop_works_for_wide_and_tall_sources(w, h, tmp_path):
    pts = {0.0: 0.3, 0.3: 0.35, 0.6: 0.7, 0.9: 0.7}
    vf = generate_ffmpeg_crop_filter(pts, 0.0, 1.0)
    assert _size_after(vf, w, h, tmp_path) == (108, 192)


def test_crop_filter_is_not_skipped_for_portrait_sources():
    assert generate_ffmpeg_crop_filter({}, 0, 1, orientation="portrait") is not None   # 4:5 used to be stretched
