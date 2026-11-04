import ast
import json
import os

import pytest

from engine import explainer_template as et

BEATS = [
    {"kind": "title", "say": "On November third a team reported evidence.", "title": "LHCb", "lines": ["Rare decay"]},
    {"kind": "counter", "say": "It happens once in ten billion decays.", "label": "1 in 10 billion"},
    {"kind": "sigma", "say": "The result is three point two sigma.", "value": 3.2, "needed": 5},
    {"kind": "scale", "say": "That is smaller than an atom.", "levels": [["an atom", "10^-10 m"], ["the zeptoverse", "10^-21 m"]]},
    {"kind": "bullets", "say": "It could point to new physics.", "lines": ["one", "two"]},
]


def test_beat_times_follow_word_timestamps():
    words = [{"word": w, "start": float(i), "end": i + 0.9} for i, w in enumerate(" ".join(b["say"] for b in BEATS).split())]
    t = et.beat_times(BEATS, words, len(words))
    assert t[0][0] == 0 and t[-1][1] == len(words)
    assert all(a[1] == b[0] for a, b in zip(t, t[1:]))
    assert t[1][0] == len(BEATS[0]["say"].split())


def test_beat_times_proportional_when_words_do_not_match():
    t = et.beat_times(BEATS, [], 40.0)
    assert t[0][0] == 0 and t[-1][1] == 40.0 and all(e > s for s, e in t)


def test_generated_scene_is_valid_python_and_ends_each_beat():
    times = et.beat_times(BEATS, [], 40.0)
    code = et.build_scene_code(BEATS, times)
    ast.parse(code)
    assert "class ExplainerScene" in code and code.count("self.until(") >= len(BEATS) * 2
    assert "10⁻²¹ m" in code                         # exponents become superscripts (no LaTeX needed)


def test_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        et.make_explainer([{"kind": "bogus", "say": "x"}], "x")


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg not on PATH")
def test_make_explainer_with_fakes(tmp_path):
    import subprocess

    def voice(text, audio, subs):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=6", audio], check=True)
        json.dump([{"word": w, "start": i * 0.2, "end": i * 0.2 + 0.15} for i, w in enumerate(text.split())], open(subs, "w"))

    def render(code):
        out = str(tmp_path / "scene.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=180x320:r=10:d=2", out], check=True)
        assert "ExplainerScene" in code
        return out

    out = et.make_explainer(BEATS[:2], str(tmp_path), voice_fn=voice, render_fn=render)
    assert os.path.isfile(out)
    assert abs(et.media_seconds(out) - 6.4) < 0.6        # the file lasts as long as the voice, not as long as the picture
