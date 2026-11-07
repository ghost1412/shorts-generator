import os
import shutil
import subprocess

import pytest

from engine import transitions as tx
from engine import trip_recap as tr
from shortsflow import web_args


def test_names_validate_and_mix_cycles_while_one_type_repeats():
    assert tx.validate("") == "auto" and tx.validate("WHIP") == "whip"
    with pytest.raises(ValueError):
        tx.validate("spin")
    assert tx.cut_types("none", 3) == [None, None, None]
    assert tx.cut_types("flash", 3) == ["flash"] * 3
    mix = tx.cut_types("mix", 8)
    assert len(set(mix)) >= 4 and mix[0] != mix[1] and all(m in tx.MIX_ORDER for m in mix)
    assert tx.seconds_for("subtle") < tx.seconds_for("medium") < tx.seconds_for("hyped") and tx.seconds_for(None) == tx.seconds_for("medium")


def test_clip_effect_builds_filters_for_the_head_and_the_tail_only():
    fx, fin, fout = tx.clip_effect("punch", "whip", 4.0, 0.2, 1920, 1080)
    assert "zoompan" in fx and "crop=1920:1080" in fx and "avgblur" in fx and fin == fout == ""
    fx, fin, fout = tx.clip_effect("flash", "glitch", 4.0, 0.2, 1920, 1080)
    assert "rgbashift" in fx and "zoompan" not in fx and "color=white" in fin and fout == ""
    assert "gt(t,3.800)" in fx and "lt(t" not in fx                      # glitch only at the tail, flash at the head
    assert tx.clip_effect(None, None, 4.0, 0.2, 1920, 1080) == ("", "", "")
    assert tx.clip_effect("flash", None, 4.0, 5.0, 1920, 1080)[1].startswith("fade=t=in:st=0:d=1.333")      # never longer than a third of the shot


def test_web_args_passes_the_transition_only_when_one_is_chosen():
    base = web_args.trip_args(["a.mp4"], "s", length=60)
    assert "--transitions" not in base
    assert web_args.trip_args(["a.mp4"], "s", length=60, transitions="mix")[-2:] == ["--transitions", "mix"]
    assert ("Zoom punch", "punch") in web_args.TRANSITION_CHOICES and web_args.TRANSITION_CHOICES[0][1] == "auto"
    assert web_args.trip_args(["a.mp4"], "s", length=60, transitions="none")[-2:] == ["--transitions", "none"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("kind", ["punch", "whip", "flash", "glitch"])
def test_a_shot_with_each_transition_renders_at_the_right_length(tmp_path, kind):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=4", "-f", "lavfi", "-i", "sine=f=300:d=4",
                    "-shortest", "-pix_fmt", "yuv420p", str(src)], check=True)
    out = tmp_path / "o.mp4"
    tr.render_clip("ffmpeg", str(src), 0, 2.0, str(out), None, "crop", (320, 180), head=kind, tail=kind, trans_s=0.3)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout)
    assert os.path.getsize(out) > 1000 and abs(dur - 2.0) < 0.15


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_recap_with_mixed_transitions_renders_end_to_end(tmp_path):
    for d in ("day1", "day2"):
        (tmp_path / d).mkdir()
        for n, tone in (("a.mp4", 300), ("b.mp4", 500)):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=30", "-f", "lavfi", "-i", f"sine=f={tone}:d=30",
                            "-shortest", "-pix_fmt", "yuv420p", str(tmp_path / d / n)], check=True)
    r = tr.make_recap([str(tmp_path / "day1"), str(tmp_path / "day2")], str(tmp_path / "out"), total_seconds=30, style="plain", aspect="16:9",
                      ask=lambda p: "{}", geocode=False, transitions="mix", edit="hype", edit_strength="medium")
    assert os.path.getsize(r["video"]) > 10000


def test_auto_follows_the_edit_style_and_explicit_choices_win():
    assert tx.resolve("auto", "hype") == "mix" and tx.resolve("auto", "vlog") == "punch"
    assert tx.resolve("auto", "podcast") == tx.resolve("auto", "educational") == tx.resolve("auto", "") == tx.resolve(None, None) == "none"
    assert tx.resolve("none", "hype") == "none" and tx.resolve("glitch", "podcast") == "glitch"
    assert tx.cut_types("auto", 3) == [None] * 3


def _footage(tmp_path):
    for d in ("day1", "day2"):
        (tmp_path / d).mkdir()
        for n, tone in (("a.mp4", 300), ("b.mp4", 500)):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=30", "-f", "lavfi", "-i", f"sine=f={tone}:d=30",
                            "-shortest", "-pix_fmt", "yuv420p", str(tmp_path / d / n)], check=True)
    return [str(tmp_path / "day1"), str(tmp_path / "day2")]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_subject_cutout_recap_makes_bridges_when_a_person_is_found(tmp_path, monkeypatch, capsys):
    import numpy as np
    from engine import subject_cut as sc
    monkeypatch.setattr(sc, "available", lambda: True)
    monkeypatch.setattr(sc, "has_person_jpegs", lambda jpegs, size=None, crop=True: True)

    def box(frame):
        m = np.zeros(frame.shape[:2], np.float32)
        h, w = m.shape
        m[h // 5:h * 4 // 5, w * 2 // 5:w * 3 // 5] = 1.0
        return m
    monkeypatch.setattr(sc, "person_mask", box)
    r = tr.make_recap(_footage(tmp_path), str(tmp_path / "out"), total_seconds=30, style="plain", aspect="16:9", ask=lambda p: "{}", geocode=False,
                      transitions="subject", edit="hype", edit_strength="medium")
    out = capsys.readouterr().out
    assert os.path.getsize(r["video"]) > 10000 and "Subject cut-out:" in out and "Subject cut-out: 0 of" not in out
    assert any(f.startswith("bridge_") for f in os.listdir(tmp_path / "out" / "recap_parts" / "subject"))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_subject_cutout_falls_back_to_normal_transitions_without_a_person(tmp_path, monkeypatch, capsys):
    from engine import subject_cut as sc
    monkeypatch.setattr(sc, "has_person_jpegs", lambda jpegs, size=None, crop=True: False)
    r = tr.make_recap(_footage(tmp_path), str(tmp_path / "out"), total_seconds=30, style="plain", aspect="16:9", ask=lambda p: "{}", geocode=False,
                      transitions="subject", edit="hype", edit_strength="medium")
    assert os.path.getsize(r["video"]) > 10000 and "Subject cut-out:" not in capsys.readouterr().out


def test_subject_look_options_reach_the_command_line_only_when_set():
    base = web_args.trip_args(["a.mp4"], "s")
    assert "--subject_look" not in base and "--subject_color" not in base
    a = web_args.trip_args(["a.mp4"], "s", subject_look="glow_sweep", subject_color="gold")
    assert a[a.index("--subject_look") + 1] == "glow_sweep" and a[a.index("--subject_color") + 1] == "gold"
    assert ("Bright outline (experimental)", "glow") in web_args.SUBJECT_LOOK_CHOICES and "gold" in web_args.SUBJECT_COLOR_CHOICES


def test_subject_max_option():
    assert "--subject_max" not in web_args.trip_args(["a.mp4"], "s")
    a = web_args.trip_args(["a.mp4"], "s", subject_max=3)
    assert a[a.index("--subject_max") + 1] == "3"
