import subprocess

import imageio_ffmpeg
import numpy as np

from engine.video_gen import FIT_CAPTION_Y, fit_caption_y, generate_ffmpeg_fit_filter

FF = imageio_ffmpeg.get_ffmpeg_exe()


def test_caption_moves_below_the_centred_picture_unless_the_user_chose():
    assert fit_caption_y(1150) == FIT_CAPTION_Y and fit_caption_y(None) == FIT_CAPTION_Y
    assert fit_caption_y(900) == 900


def test_filter_shape():
    f = generate_ffmpeg_fit_filter(1080, 1920)
    assert f.startswith("split=2") and "boxblur" in f and "overlay=(W-w)/2:(H-h)/2" in f and f.endswith("format=yuv420p")
    assert generate_ffmpeg_fit_filter(108, 192, "crop=100:50:0:0").startswith("crop=100:50:0:0,split=2")


def _frame(vf, src_w, src_h, tmp_path):
    out = tmp_path / "o.raw"
    r = subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={src_w}x{src_h}:rate=10:duration=1",
                        "-vf", vf, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
    return np.fromfile(out, dtype=np.uint8).reshape(192, 108, 3)


def test_a_landscape_source_is_shown_whole_over_a_blurred_background(tmp_path):
    img = _frame(generate_ffmpeg_fit_filter(108, 192), 320, 180, tmp_path)
    assert img.shape == (192, 108, 3)
    top, bottom = img[:20], img[-20:]
    assert top.mean() > 25 and bottom.mean() > 25                       # not black bars: a blurred copy fills the frame
    middle = img[192 // 2 - 25: 192 // 2 + 25]
    assert float(middle.std()) > float(top.std()) * 1.5               # the sharp picture in the middle has more detail than the blur
