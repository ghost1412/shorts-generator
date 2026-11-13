import os
import shutil
import subprocess

import pytest

from engine import overlay


def test_wanted_and_plan():
    assert not overlay.wanted({}) and not overlay.wanted({"segmentTransition": "iris"})
    assert overlay.wanted({"introAnimation": "tiles"}) and overlay.wanted({"visualTemplate": "neon-frame"})
    both = {"visualTemplate": "podcast-card"}
    assert overlay.plan(600.0, both) == [(0.0, overlay.HEAD_SECONDS), (597.0, overlay.TAIL_SECONDS)]
    assert overlay.plan(600.0, {"introAnimation": "tiles"}) == [(0.0, overlay.HEAD_SECONDS)]
    assert overlay.plan(600.0, {"outroAnimation": "iris"}) == [(597.0, overlay.TAIL_SECONDS)]
    assert overlay.plan(8.0, both) == [(0.0, 8.0)]                       # a short video gets one piece over its whole length
    assert overlay.plan(600.0, {}) == [] and overlay.plan(5.0, {}) == []


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_composite_lays_a_transparent_piece_over_the_video_at_its_start_time(tmp_path):
    from PIL import Image
    base, piece, out = str(tmp_path / "base.mp4"), str(tmp_path / "piece.mov"), str(tmp_path / "out.mp4")
    run = lambda *a: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)
    run("-f", "lavfi", "-i", "color=c=0x202020:s=320x180:d=4:r=30", "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", base)
    # a 1 s piece: a fully opaque red block in the top-left quarter, transparent elsewhere
    run("-f", "lavfi", "-i", "color=c=black@0.0:s=320x180:d=1:r=30,format=yuva444p,drawbox=x=0:y=0:w=160:h=90:color=red@1:t=fill:replace=1", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", piece)
    assert overlay.composite(base, [(piece, 2.0)], out)
    assert abs(overlay.probe(out)[2] - 4.0) < 0.2 and overlay.probe(out)[:2] == (320, 180)

    def pixel(t, xy):
        png = str(tmp_path / f"f{t}.png")
        run("-ss", str(t), "-i", out, "-frames:v", "1", png)
        return Image.open(png).convert("RGB").getpixel(xy)
    before, during, after = pixel(1.0, (40, 40)), pixel(2.5, (40, 40)), pixel(3.5, (40, 40))
    assert during[0] > 180 and during[1] < 80                            # red while the piece is on
    assert before[0] < 80 and after[0] < 80                              # the plain video before and after it
    assert pixel(2.5, (250, 150))[0] < 80                                # outside the block the picture shows through
    audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", out], capture_output=True, text=True).stdout
    assert "aac" in audio                                                # the audio is kept


def test_apply_leaves_the_video_alone_when_nothing_is_chosen(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    assert overlay.apply_to_video(str(f), {}) is False and f.read_bytes() == b"x"
    assert overlay.apply_to_video(str(f), {"introAnimation": "tiles"}, log=lambda *_: None) is False      # unreadable video: skipped, not a crash
