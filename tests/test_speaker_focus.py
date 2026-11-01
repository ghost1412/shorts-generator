import subprocess

import pytest

from engine.speaker_focus import build_active_speaker_filter, shots_from_decisions

CX = {"L": 0.25, "R": 0.75, "y": {"L": 0.4, "R": 0.45}}


def run(decisions, step=0.2, duration=None):
    times = [i * step for i in range(len(decisions))]
    return shots_from_decisions(times, decisions, duration or len(decisions) * step)


def test_holds_minimum_dwell_and_persistence():
    # L for 1 s, then R from 1 s on: the cut must wait until the first shot has lasted 2.5 s
    shots = run(["L"] * 5 + ["R"] * 45)
    assert [s["target"] for s in shots] == ["L", "R"]
    assert shots[1]["start"] == pytest.approx(2.5)


def test_brief_flicker_does_not_cut():
    shots = run(["L"] * 20 + ["R"] * 2 + ["L"] * 28)  # R for only 0.4 s
    assert [s["target"] for s in shots] == ["L"]


def test_every_shot_respects_min_dwell():
    pattern = (["L"] * 4 + ["R"] * 4) * 20  # rapid alternation
    shots = run(pattern)
    assert all(s["end"] - s["start"] >= 2.5 - 1e-9 for s in shots)


def test_uncertain_start_uses_split():
    assert run([None] * 10 + ["split"] * 40)[0]["target"] == "split"


def test_short_tail_is_merged():
    shots = run(["L"] * 40 + ["R"] * 6)  # R would last 1.2 s at the end
    assert [s["target"] for s in shots] == ["L"]
    assert shots[-1]["end"] == pytest.approx(46 * 0.2)


def test_filter_renders_with_ffmpeg(tmp_path):
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    shots = [dict(s, cx=CX) for s in [
        {"start": 0, "end": 1, "target": "L"},
        {"start": 1, "end": 2, "target": "split"},
        {"start": 2, "end": 3, "target": "R"},
    ]]
    vf = build_active_speaker_filter(shots)
    out = tmp_path / "out.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=3",
                    "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", str(out)], check=True)
    probe = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(out)],
                           capture_output=True, text=True).stderr
    assert "1080x1920" in probe


def _visual(n, speakers):
    """Face motion where the real speaker's face is busier."""
    return [{"L": 2.0 if sp == "L" else 0.8, "R": 2.0 if sp == "R" else 0.8} for sp in speakers]


def test_diarize_by_pitch_separates_two_voices():
    import numpy as np
    from engine.speaker_focus import diarize_by_pitch
    truth = ["R"] * 15 + ["L"] * 15 + ["R"] * 10   # R = low voice (120 Hz), L = high voice (210 Hz)
    f0 = [120.0 if t == "R" else 210.0 for t in truth]
    f0[3] = float("nan")  # one unvoiced blip
    out = diarize_by_pitch(f0, [1.0] * len(truth), _visual(len(truth), truth))
    assert out[10] == "R" and out[20] == "L" and out[35] == "R"
    assert out[3] is None or out[3] == "R"
    assert np.mean([a == b for a, b in zip(out, truth) if a]) > 0.95


def test_diarize_by_pitch_maps_voices_to_the_other_faces_too():
    from engine.speaker_focus import diarize_by_pitch
    truth = ["L"] * 15 + ["R"] * 15   # now the LEFT face has the low voice
    f0 = [120.0 if t == "L" else 210.0 for t in truth]
    out = diarize_by_pitch(f0, [1.0] * 30, _visual(30, truth))
    assert out[5] == "L" and out[25] == "R"


def test_diarize_by_pitch_declines_similar_voices_and_silence():
    from engine.speaker_focus import diarize_by_pitch
    assert diarize_by_pitch([130.0 + (i % 3) for i in range(40)], [1.0] * 40, [{}] * 40) is None
    assert diarize_by_pitch([float("nan")] * 40, [1.0] * 40, [{}] * 40) is None


def test_quiet_samples_have_no_opinion():
    from engine.speaker_focus import diarize_by_pitch
    f0 = [120.0] * 12 + [210.0] * 12
    out = diarize_by_pitch(f0, [0.05] * 4 + [1.0] * 20, _visual(24, ["L"] * 12 + ["R"] * 12))
    assert out[:4] == [None] * 4
