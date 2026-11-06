import os
import shutil
import subprocess

import pytest

from engine import transitions as tx
from engine import trip_recap as tr
from shortsflow import web_args


def test_names_validate_and_mix_cycles_while_one_type_repeats():
    assert tx.validate("") == "none" and tx.validate("WHIP") == "whip"
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
    assert ("Zoom punch", "punch") in web_args.TRANSITION_CHOICES and web_args.TRANSITION_CHOICES[0][1] == "none"


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
