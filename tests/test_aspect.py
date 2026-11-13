import shutil
import subprocess

import pytest

from engine import aspect, video_gen


def test_sizes_fractions_and_crops():
    assert aspect.size("9:16") == (1080, 1920) and aspect.size("1:1") == (1080, 1080) and aspect.size("4:5") == (1080, 1350)
    assert aspect.size("16:9") == (1920, 1080) and aspect.size(None) == (1080, 1920) and aspect.size("7:3") == (1080, 1920)
    assert [aspect.fraction(*aspect.size(r)) for r in aspect.NAMES] == ["9/16", "1/1", "4/5", "16/9"]
    # the 9:16 crop is exactly what it always was
    assert aspect.center_crop(1080, 1920) == video_gen.CENTER_CROP_9X16
    assert aspect.crop_exprs(1080, 1920) == ("min(iw,ih*9/16)", "min(ih,iw*16/9)")
    assert aspect.crop_exprs(1080, 1080) == ("min(iw,ih*1/1)", "min(ih,iw*1/1)")


def test_caption_heights_follow_the_frame():
    assert aspect.scale_y(1150, "9:16") == 1150 and aspect.scale_y(1150, 1920) == 1150
    assert aspect.scale_y(1150, "1:1") == 647 and aspect.scale_y(1150, "4:5") == 809 and aspect.scale_y(1150, "16:9") == 647


def test_the_face_tracked_crop_keeps_its_9x16_text_and_follows_other_shapes():
    pts = {0.0: 0.5, 1.0: 0.5, 2.0: 0.6}
    nine = video_gen.generate_ffmpeg_crop_filter(pts, 0.0, 2.0)
    assert "min(iw,ih*9/16)" in nine and "min(ih,iw*16/9)" in nine
    sq = video_gen.generate_ffmpeg_crop_filter(pts, 0.0, 2.0, 1080, 1080)
    assert "min(iw,ih*1/1)" in sq and "9/16" not in sq
    assert video_gen.generate_ffmpeg_crop_filter(None, 0.0, 2.0, 1920, 1080).endswith(aspect.center_crop(1920, 1080))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
@pytest.mark.parametrize("ratio", ["9:16", "1:1", "4:5", "16:9"])
def test_every_layout_filter_makes_the_asked_size(tmp_path, ratio):
    w, h = aspect.size(ratio)
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:d=1:r=30", "-pix_fmt", "yuv420p", src], check=True)
    pts = {0.0: 0.4, 0.5: 0.5, 1.0: 0.6}
    chains = {
        "single": video_gen.generate_ffmpeg_crop_filter(pts, 0.0, 1.0, w, h) + f",scale={w}:{h},format=yuv420p",
        "centre": f"{aspect.center_crop(w, h)},scale={w}:{h},format=yuv420p",
    }
    fit = video_gen.generate_ffmpeg_fit_filter(w, h)
    split = video_gen.generate_ffmpeg_split_screen_filter(w, h)
    for name, vf in chains.items():
        out = str(tmp_path / f"{name}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", vf, "-frames:v", "5", out], check=True)
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
        assert probe == f"{w},{h}", (ratio, name, probe)
    for name, graph in (("fit", fit), ("split", split)):
        out = str(tmp_path / f"{name}.mp4")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", graph, "-map", "[v]" if "[v]" in graph else "[out]", "-frames:v", "5", out], capture_output=True, text=True)
        if r.returncode != 0:                      # these helpers name their last pad differently; fall back to the default output label
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", graph, "-frames:v", "5", out], capture_output=True, text=True)
        assert r.returncode == 0, (ratio, name, r.stderr[-300:])
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
        assert probe == f"{w},{h}", (ratio, name, probe)
