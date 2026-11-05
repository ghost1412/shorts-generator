"""Auto enhance: measure a clip, correct only what is off (offline; FFmpeg only for the render checks)."""
import os
import shutil
import subprocess

import numpy as np
import pytest

from engine import enhance, trip_recap as tr


def frame(color, size=24, noise=0.0, seed=1):
    img = np.empty((size, size, 3), np.float32)
    img[:] = color
    if noise:
        img += np.random.default_rng(seed).normal(0, noise, img.shape).astype(np.float32)
    return np.clip(img, 0, 1)


def ramp(lo, hi, size=32, tint=(1.0, 1.0, 1.0)):
    """A horizontal brightness ramp from lo to hi: a picture with a real spread of tones."""
    row = np.linspace(lo, hi, size, dtype=np.float32)
    img = np.repeat(row[None, :, None], size, axis=0).repeat(3, axis=2)
    return np.clip(img * np.array(tint, np.float32), 0, 1)


def test_measure_reports_tones_cast_and_saturation():
    st = enhance.measure([ramp(0.1, 0.9)])
    assert st["p1"] < 0.15 and 0.4 < st["p50"] < 0.6 and st["p99"] > 0.85 and st["sat"] < 0.01
    assert enhance.measure([]) is None
    grey_blue = enhance.measure([ramp(0.1, 0.9, tint=(0.8, 0.9, 1.2))])
    assert grey_blue["b"] > grey_blue["r"]


def test_a_well_exposed_clip_gets_no_tone_or_colour_corrections():
    p = enhance.plan(enhance.measure([ramp(0.1, 0.9)]))
    assert p["gamma"] == 1.0 and p["black"] == 0.0 and p["white"] == 1.0 and p["cast"] == (0.0, 0.0, 0.0)
    assert not any(n.startswith(("too", "flat", "colour cast")) for n in p["notes"])       # (a pure grey ramp counts as dull: colour only)


def test_dark_clip_is_lifted_and_bright_clip_toned_down_within_limits():
    dark = enhance.plan(enhance.measure([ramp(0.0, 0.35)]))
    assert 1.0 < dark["gamma"] <= 1.7 and "too dark, lifted" in dark["notes"]
    bright = enhance.plan(enhance.measure([ramp(0.5, 1.0)]))
    assert 0.85 <= bright["gamma"] < 1.0
    black = enhance.plan(enhance.measure([frame(0.01)]))
    assert black["gamma"] <= 1.7                                    # a black frame cannot send the gamma to infinity


def test_flat_clip_gets_its_range_stretched_but_a_normal_one_does_not():
    flat = enhance.plan(enhance.measure([ramp(0.35, 0.75)]))
    assert flat["black"] > 0 and flat["white"] < 1.0 and "flat, contrast stretched" in flat["notes"]
    normal = enhance.plan(enhance.measure([ramp(0.10, 0.88)]))
    assert normal["black"] == 0.0 and normal["white"] == 1.0          # ordinary phone footage spans about 0.1-0.9: left alone


def test_a_grey_clip_with_a_cast_is_corrected_but_a_vivid_warm_scene_is_not():
    cast = enhance.plan(enhance.measure([ramp(0.15, 0.85, tint=(0.80, 0.95, 1.15))]))
    assert cast["cast"][2] < 0 < cast["cast"][0] and "colour cast reduced" in cast["notes"]      # less blue, more red
    assert all(abs(v) <= 0.06 for v in cast["cast"])
    sunset = frame((0.9, 0.45, 0.1), size=24)
    sunset[:, :12] *= 0.4
    assert enhance.plan(enhance.measure([sunset]))["cast"] == (0.0, 0.0, 0.0)               # the warm colour IS the look


def test_dull_clip_gets_a_little_colour_and_subtle_is_gentler_than_medium():
    dull = enhance.measure([ramp(0.15, 0.85, tint=(1.0, 0.98, 0.97))])
    p_med, p_sub = enhance.plan(dull, "medium"), enhance.plan(dull, "subtle")
    assert p_med["saturation"] > p_sub["saturation"] > 1.0
    dark = enhance.measure([ramp(0.0, 0.35)])
    assert enhance.plan(dark, "medium")["gamma"] > enhance.plan(dark, "subtle")["gamma"] > 1.0
    assert enhance.plan(dark, 0)["gamma"] == 1.0 and enhance.plan(None)["notes"] == []


def test_noise_is_only_denoised_when_the_clip_is_dark():
    noisy_dark = enhance.plan(enhance.measure([frame(0.15, size=48, noise=0.06)]))
    assert noisy_dark["denoise"] is True
    noisy_bright = enhance.plan(enhance.measure([frame(0.6, size=48, noise=0.06)]))
    assert noisy_bright["denoise"] is False


def test_build_filter_is_empty_only_without_any_correction():
    assert enhance.build_filter({"gamma": 1.0, "black": 0.0, "white": 1.0, "cast": (0, 0, 0), "saturation": 1.0, "sharpen": 0.0, "denoise": False}) == ""
    vf = enhance.build_filter(enhance.plan(enhance.measure([ramp(0.0, 0.35)])))
    assert "eq=gamma=" in vf and "unsharp" in vf


FF = shutil.which("ffmpeg")


@pytest.mark.skipif(not FF, reason="needs ffmpeg")
def test_the_filter_chain_runs_in_ffmpeg_and_really_brightens_a_dark_clip(tmp_path):
    src = str(tmp_path / "dark.mp4")
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:d=2:r=10,lutyuv=y=val*0.4", "-pix_fmt", "yuv420p", src], check=True)       # a dark but varied picture, the same on every FFmpeg
    vf, plan, stats = enhance.enhance_filter(src, "medium", FF)
    assert vf and "too dark, lifted" in plan["notes"]
    out = str(tmp_path / "fixed.mp4")
    enhance.render(src, out, "medium", FF)
    before, after = enhance.measure(enhance.sample_frames(src, FF, n=3)), enhance.measure(enhance.sample_frames(out, FF, n=3))
    assert after["p50"] > before["p50"] + 0.03                      # measurably brighter


@pytest.mark.skipif(not FF, reason="needs ffmpeg")
def test_render_clip_applies_the_correction_before_the_look(tmp_path):
    src = str(tmp_path / "a.mp4")
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x303030:s=320x180:d=2:r=10", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "2", "-pix_fmt", "yuv420p", src], check=True)
    old = (tr.W, tr.H)
    tr.W, tr.H = 320, 180
    try:
        out = str(tmp_path / "o.mp4")
        tr.render_clip(FF, src, 0, 1.0, out, None, "crop", (320, 180), audio=False, grade="eq=saturation=1.05", fix="eq=gamma=1.4")
        assert os.path.isfile(out)
        assert enhance.measure(enhance.sample_frames(out, FF, n=2))["p50"] > enhance.measure(enhance.sample_frames(src, FF, n=2))["p50"]
    finally:
        tr.W, tr.H = old


def test_cli_and_web_options_exist():
    from shortsflow import web_args
    assert "--enhance" not in web_args.trip_args(["a.mp4"], "s")
    a = web_args.trip_args(["a.mp4"], "s", enhance=True)
    assert a[a.index("--enhance") + 1] == "auto"
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shortsflow", "_main.py"), encoding="utf-8").read()
    assert '"--enhance"' in src and '"--enhance_strength"' in src


@pytest.mark.skipif(not FF, reason="needs ffmpeg")
def test_make_recap_with_enhance_brightens_a_dark_trip_video(tmp_path):
    (tmp_path / "day1").mkdir()
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=640x360:d=20:r=10,lutyuv=y=val*0.4", "-f", "lavfi", "-i", "sine=f=300:d=20",
                    "-shortest", "-pix_fmt", "yuv420p", str(tmp_path / "day1" / "a.mp4")], check=True)
    results = {}
    for mode in ("off", "auto"):
        res = tr.make_recap([str(tmp_path / "day1")], str(tmp_path / mode), trip_name="T", total_seconds=12, style="plain", aspect="16:9",
                            ask=lambda p: "{}", geocode=False, enhance=mode)
        results[mode] = enhance.measure(enhance.sample_frames(res["video"], FF, n=4))["p50"]
    assert results["auto"] > results["off"] + 0.03


def _fake_extract(monkeypatch, tmp_path, **kw):
    """Run extract_segments with a fake FFmpeg process and return (the ffmpeg commands, the highlights list)."""
    import json
    from engine import video_gen
    cmds = []

    class FakeProc:
        def __init__(self, cmd, **k):
            cmds.append(cmd)

        def wait(self):
            return 0

    monkeypatch.setattr(video_gen.subprocess, "Popen", FakeProc)
    monkeypatch.setattr(video_gen, "_check_nvenc", lambda: False)
    monkeypatch.setattr(video_gen, "generate_thumbnail", lambda *a, **k: None, raising=False)
    tr = tmp_path / "t.json"
    tr.write_text(json.dumps({}))
    out = tmp_path / "out"
    out.mkdir()
    highlights = [{"start": 2.0, "end": 7.0}]
    try:
        video_gen.extract_segments("src.mp4", highlights, str(tr), str(out), **kw)
    except Exception:
        pass            # post-processing after the FFmpeg command is irrelevant here
    return cmds, highlights


def test_clip_extraction_measures_the_clip_and_puts_the_correction_first(monkeypatch, tmp_path):
    seen = {}

    def fake(video, strength="medium", ffmpeg=None, frames=None, start=0.0, duration=None):
        seen.update(video=video, strength=strength, start=start, duration=duration)
        return "eq=gamma=1.4", {"notes": ["too dark, lifted"]}, {}
    monkeypatch.setattr(enhance, "enhance_filter", fake)
    cmds, highlights = _fake_extract(monkeypatch, tmp_path, enhance="auto", enhance_strength="subtle")
    vf = cmds[0][cmds[0].index("-vf") + 1]
    assert vf.startswith("eq=gamma=1.4,")                                         # corrected before cropping / any look
    assert seen == {"video": "src.mp4", "strength": "subtle", "start": 2.0, "duration": 5.0}      # this clip's stretch, not the whole video
    assert highlights[0]["enhance_notes"] == ["too dark, lifted"]


def test_clip_extraction_without_enhance_is_unchanged(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("must not measure anything when enhance is off")
    monkeypatch.setattr(enhance, "enhance_filter", boom)
    cmds, highlights = _fake_extract(monkeypatch, tmp_path)
    assert "eq=gamma" not in cmds[0][cmds[0].index("-vf") + 1] and "enhance_notes" not in highlights[0]


def test_a_failed_measurement_leaves_the_clip_alone(monkeypatch, tmp_path):
    def broken(*a, **k):
        raise RuntimeError("no frames")
    monkeypatch.setattr(enhance, "enhance_filter", broken)
    cmds, highlights = _fake_extract(monkeypatch, tmp_path, enhance="auto")
    assert cmds and "enhance_notes" not in highlights[0]


def test_sample_frames_can_look_at_a_stretch_of_a_longer_video(tmp_path):
    seen = []

    class R:
        returncode = 0
        stdout = bytes(24 * 24 * 3)

    def run(cmd, **k):
        seen.append(float(cmd[cmd.index("-ss") + 1]) if "-ss" in cmd else None)
        return R()
    frames = enhance.sample_frames("v.mp4", "ffmpeg", n=2, width=24, duration=10.0, start=100.0, run=run)
    assert len(frames) == 2 and all(100.0 < t < 110.0 for t in seen)             # inside [start, start + duration]


def test_a_reference_brightness_makes_neighbouring_shots_match():
    dark_shot = enhance.measure([ramp(0.0, 0.40)])             # median 0.2
    ok_shot = enhance.measure([ramp(0.20, 0.80)])              # median 0.5
    brightish = enhance.measure([ramp(0.35, 0.85)])            # median 0.6: fine on its own
    assert enhance.plan(ok_shot, "medium", reference=0.5)["gamma"] == 1.0                      # already at the recap's typical brightness
    assert enhance.plan(dark_shot, "medium", reference=0.5)["gamma"] > enhance.plan(dark_shot, "medium")["gamma"] > 1.0   # lifted further towards the others
    assert enhance.plan(brightish, "medium")["gamma"] == 1.0                                   # inside the default band
    assert enhance.plan(brightish, "medium", reference=0.35)["gamma"] < 1.0                    # but a bright one among darker shots is toned down
