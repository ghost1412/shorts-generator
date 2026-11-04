import json
import os

from engine import auto_zoom as az
from shortsflow import web_args

REMOTION = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "remotion-video", "src")


def _words(text, step=0.4, start=0.0, gaps=None):
    """Build word dicts from text; `gaps` maps a word index to an extra pause before it."""
    out, t = [], start
    for i, w in enumerate(text.split()):
        t += (gaps or {}).get(i, 0.0)
        out.append({"word": w, "start": round(t, 3), "end": round(t + 0.3, 3)})
        t += step
    return out


def test_emphasis_strength_numbers_and_curiosity():
    assert az.emphasis_strength("$200") == 3
    assert az.emphasis_strength("50%") == 3
    assert az.emphasis_strength("million,") == 2
    assert az.emphasis_strength("Secret!") == 2
    assert az.emphasis_strength("the") == 0
    assert az.emphasis_strength("") == 0


def test_no_moments_for_empty_short_or_zero_intensity():
    words = _words("you waste $200 a month on things")
    assert az.choose_zoom_moments([], 20) == []
    assert az.choose_zoom_moments(words, 0.5) == []
    assert az.choose_zoom_moments(words, 20, intensity=0) == []


def test_punch_on_number_and_push_on_sentence_start():
    # a long enough clip with a number early and a sentence start after a full stop later
    words = _words("most people waste $200 every month. Here is the thing nobody tells you about money", gaps={6: 0.2})
    moments = az.choose_zoom_moments(words, 12.0)
    assert moments
    starts = [m["start"] for m in moments]
    number_t = next(w["start"] for w in words if w["word"] == "$200")
    assert any(abs(s - (number_t - 0.05)) < 0.01 for s in starts)  # the punch lands on the number
    punch = next(m for m in moments if abs(m["start"] - (number_t - 0.05)) < 0.01)
    assert punch["rise"] == az.PUNCH_RISE and 1.0 < punch["scale"] <= 1.1


def test_moments_sorted_spaced_and_inside_the_clip():
    words = _words(" ".join(["wow 100 secret 5 million never mistake"] * 6), step=0.35)
    duration = words[-1]["end"] + 0.5
    moments = az.choose_zoom_moments(words, duration)
    assert moments
    for a, b in zip(moments, moments[1:]):
        assert b["start"] - a["start"] >= az.MIN_SPACING - 0.06
        assert b["start"] >= a["end"]                      # never overlapping
    for m in moments:
        assert 0 <= m["start"] < m["end"] <= duration
        assert m["end"] - m["start"] >= 0.4


def test_intensity_scales_the_zoom_and_default_is_subtle():
    words = _words("this costs $500 today and that is a lot", gaps={})
    base = az.choose_zoom_moments(words, 10.0)[0]["scale"]
    double = az.choose_zoom_moments(words, 10.0, intensity=2.0)[0]["scale"]
    assert 1.0 < base <= 1.1
    assert abs((double - 1.0) - 2 * (base - 1.0)) < 0.001


def test_energy_peak_boosts_a_plain_word_into_a_punch():
    words = _words("so this really matters because everyone often forgets it")
    plain = az.choose_zoom_moments(words, 10.0)
    peak_t = words[3]["start"]  # "matters"
    boosted = az.choose_zoom_moments(words, 10.0, peaks=[peak_t])
    assert any(abs(m["start"] - (peak_t - 0.05)) < 0.01 for m in boosted)
    assert not any(abs(m["start"] - (peak_t - 0.05)) < 0.01 and m["rise"] == az.PUNCH_RISE for m in plain)


def test_zoom_scale_envelope():
    m = [{"start": 2.0, "end": 3.0, "scale": 1.1, "rise": 0.1}]
    assert az.zoom_scale_at(1.9, m) == 1.0
    assert az.zoom_scale_at(2.0, m) == 1.0
    assert abs(az.zoom_scale_at(2.1, m) - 1.1) < 1e-9          # at the peak after the rise
    assert abs(az.zoom_scale_at(2.6, m) - 1.1) < 1e-9          # held
    assert 1.0 < az.zoom_scale_at(3.2, m) < 1.1                # easing back
    assert az.zoom_scale_at(3.0 + az.RETURN_SECONDS + 0.01, m) == 1.0
    assert az.zoom_scale_at(5, []) == 1.0


def test_energy_peaks_never_raises(tmp_path):
    assert az.energy_peaks(str(tmp_path / "missing.wav")) == []


def test_zoom_moments_are_json_serialisable():
    words = _words("you pay $20 a month for that")
    json.dumps(az.choose_zoom_moments(words, 8.0))


def test_extras_args_auto_zoom_needs_remotion():
    assert "--auto_zoom" in web_args.extras_args(auto_zoom=True, use_remotion=True)
    assert "--auto_zoom" not in web_args.extras_args(auto_zoom=True, use_remotion=False)
    assert web_args.extras_args() == []


def test_remotion_side_mirrors_the_python_envelope():
    ts = open(os.path.join(REMOTION, "autoZoom.ts"), encoding="utf-8").read()
    assert f"RETURN_SECONDS = {az.RETURN_SECONDS}" in ts
    shortflow = open(os.path.join(REMOTION, "ShortFlow.tsx"), encoding="utf-8").read()
    assert "zoomMoments" in shortflow and "zoomScaleAt" in shortflow


def test_renderer_adds_zoom_props_only_when_asked():
    import engine.remotion_renderer as rr
    src = open(rr.__file__, encoding="utf-8").read()
    assert "auto_zoom=False" in src and 'props["zoomMoments"]' in src


def test_fill_gaps_adds_a_push_in_the_middle_of_long_calm_stretches():
    from engine.auto_zoom import fill_gaps
    moments = [{"start": 2.0, "end": 3.1, "scale": 1.08, "rise": 0.12}]
    out = fill_gaps(moments, 30.0, max_gap=7.0)
    assert len(out) == 2 and out[0] == moments[0]                                   # existing moment kept as it was
    fill = out[1]
    assert 3.1 + 0.8 <= fill["start"] and fill["end"] <= 29.7 and abs((fill["start"] + fill["end"]) / 2 - 16.55) < 0.1
    assert fill["scale"] == 1.05 and fill["rise"] > 1.0                             # a slow push, subtle
    assert fill_gaps(moments, 8.0, max_gap=7.0) == moments                           # nothing long enough to fill
    assert fill_gaps([], 0, max_gap=7.0) == [] and fill_gaps(moments, 30.0, intensity=0) == moments
    dense = [{"start": float(t), "end": t + 1.0, "scale": 1.08, "rise": 0.12} for t in (1, 5, 9, 13)]
    assert fill_gaps(dense, 15.0, max_gap=7.0) == dense                              # gaps of 4 s: untouched
