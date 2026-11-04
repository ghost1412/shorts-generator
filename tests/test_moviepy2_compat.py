"""MoviePy 2 replacements for calls that used to fail silently (MoviePy 1 names)."""
import os
import numpy as np
from moviepy import VideoClip, vfx
from PIL import Image


def test_loop_effect_extends_a_short_clip():
    clip = VideoClip(lambda t: np.zeros((8, 8, 3), dtype="uint8"), duration=1.0).with_fps(10)
    assert clip.with_effects([vfx.Loop(duration=3.0)]).duration == 3.0   # vfx.loop(...) is MoviePy 1


def test_custom_image_background_becomes_a_video(tmp_path):
    from engine.media_gen import download_background_video
    img = tmp_path / "bg.jpg"
    Image.fromarray((np.random.rand(37, 51, 3) * 255).astype("uint8")).save(img)   # odd size on purpose
    out = tmp_path / "bg.mp4"
    got = download_background_video("anything", output_path=str(out), custom_bg=str(img))
    assert got and os.path.getsize(got) > 1000
    assert open(got, "rb").read(12)[4:8] == b"ftyp"      # a real mp4, not the copied JPEG
