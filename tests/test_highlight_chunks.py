import json

from engine import analysis
from engine.highlight_chunks import clamp_to_chunk, per_chunk_count, plan_chunks, segments_in


def test_short_video_is_one_stretch():
    assert plan_chunks(900) == [(0.0, 900.0)]


def test_long_video_is_covered_without_gaps():
    chunks = plan_chunks(3842)
    assert 2 <= len(chunks) <= 8
    assert chunks[0][0] == 0 and chunks[-1][1] == 3842
    assert all(a[1] == b[0] for a, b in zip(chunks, chunks[1:]))
    assert len(plan_chunks(20 * 3600)) == 8              # bounded number of requests


def test_per_chunk_count():
    assert per_chunk_count(5, 1) == 5
    assert per_chunk_count(10, 7) == 3
    assert per_chunk_count(1, 8) == 2


def test_clamp_to_chunk():
    assert clamp_to_chunk({"start": 16596, "end": 16636}, 0, 640) is None          # invented time past the stretch
    assert clamp_to_chunk({"start": 700, "end": 740}, 0, 640) is None              # belongs to another stretch
    assert clamp_to_chunk({"start": 5, "end": 3}, 0, 640) is None
    assert clamp_to_chunk("nonsense", 0, 640) is None
    h = clamp_to_chunk({"start": 620, "end": 670, "x": 1}, 0, 640)
    assert (h["start"], h["end"], h["x"]) == (620, 640, 1)


def test_segments_in():
    segs = [{"start": 0, "end": 10}, {"start": 595, "end": 605}, {"start": 700, "end": 710}]
    assert len(segments_in(segs, 0, 600)) == 1 and len(segments_in(segs, 600, 1200)) == 2   # a segment belongs where its middle is


def test_identify_highlights_asks_each_stretch(tmp_path, monkeypatch):
    # a 40-minute transcript: the model answers for each stretch, one answer is invented past the end
    segs = [{"start": float(t), "end": float(t + 8), "text": f"sentence number {t} is here"} for t in range(0, 2400, 10)]
    p = tmp_path / "transcript.json"
    p.write_text(json.dumps({"segments": segs}), encoding="utf-8")
    asked = []

    def fake_llm(prompt, system=None, max_tokens=None, **kw):
        import re
        times = [float(x) for x in re.findall(r"\[(\d+\.\d+)s - ", prompt)]
        asked.append((min(times), max(times)))
        lo = min(times) + 20
        return ('START_JSON[{"start": %s, "end": %s, "viral_score": 80, "hook_text": "h", "tone": "tense"},'
                ' {"start": 16596, "end": 16636, "viral_score": 90, "hook_text": "bad", "tone": "tense"}]END_JSON' % (lo, lo + 30))

    import engine.script_gen as sg
    monkeypatch.setattr(sg, "get_llm_response", fake_llm)
    out = analysis.identify_highlights(str(p), video_path=None, clip_count=6, mode="shorts", target_duration=30,
                                       min_duration=15, diversity=False, extra_signals=False)
    assert len(asked) >= 3                                   # one request per stretch
    assert all(hi - lo <= 2400 / len(asked) + 60 for lo, hi in asked)   # each prompt only holds its own stretch
    assert out and all(h["end"] <= 2400 for h in out)       # the invented time never gets through
    starts = sorted(h["start"] for h in out)
    assert starts[-1] > 1500                                 # the end of the video is represented


def test_long_highlights_without_any_llm_still_fill_the_target(tmp_path, monkeypatch):
    # a failing single-window LLM call used to return one fixed 30 s slot (a 33 s reel for a 180 s target)
    segs = [{"start": float(t), "end": float(t + 8), "text": f"sentence number {t} is here"} for t in range(0, 900, 10)]
    p = tmp_path / "transcript.json"
    p.write_text(json.dumps({"segments": segs}), encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("no provider answered")

    import engine.script_gen as sg
    monkeypatch.setattr(sg, "get_llm_response", boom)
    out = analysis.identify_highlights(str(p), video_path=None, clip_count=5, mode="long", target_duration=180,
                                       min_duration=15, diversity=False, extra_signals=False)
    total = sum(h["end"] - h["start"] for h in out)
    assert 0.85 * 180 <= total <= 1.12 * 180, total
