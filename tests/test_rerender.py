import json
import os
import sys
import types

import pytest

from engine import rerender


def test_window_validation_gives_plain_reasons():
    assert rerender.validate_window("5", "20") == (5.0, 20.0)
    for args, reason in [(("a", 10), "numbers"), ((-1, 10), "before the beginning"), ((5, 6), "at least"),
                         ((0, 500), "at most"), ((0, 99), "past the end")]:
        src = 60 if reason == "past the end" else None
        with pytest.raises(ValueError, match=reason):
            rerender.validate_window(*args, source_seconds=src)


def _session(tmp_path, with_source=True):
    session = tmp_path / "sessions" / "run"
    session.mkdir(parents=True)
    (session / "video_clip_1.mp4").write_bytes(b"old video")
    (session / "video_clip_1.jpg").write_bytes(b"thumb")
    (session / "transcript.json").write_text("{}")
    (session / "interest_points.json").write_text(json.dumps({"5.0": 50, "6.0": 52, "7.0": 51, "8.0": 49, "9.0": 50, "10.0": 50}))
    (session / "silence_intervals.json").write_text(json.dumps([[0, 4], [5, 12]]))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"src")
    results = {"source_video": str(source) if with_source else "", "settings": {
        "extract_mode": "shorts", "layout": "single", "smart_crop": True, "tighten": True, "tighten_mode": "cut",
        "use_remotion": True, "caption_style": "HORMOZI", "subtitle_y_pos": 1150, "brand": None},
        "clips": [{"clip_index": 1, "video_path": "sessions/run/video_clip_1.mp4", "start": 5.0, "end": 14.0, "duration": 9.0,
                   "thumbnail": "video_clip_1.jpg"}]}
    (session / "results.json").write_text(json.dumps(results))
    return session


def _fake_engine(monkeypatch, calls):
    analysis = types.ModuleType("engine.analysis")
    analysis.detect_letterbox = lambda p: None
    analysis.detect_orientation = lambda p: "landscape"
    analysis.probe_duration = lambda p: 100.0

    def detect_interest_points(p, segments=None):
        calls["analysed"] = segments
        return {}
    analysis.detect_interest_points = detect_interest_points
    video = types.ModuleType("engine.video_gen")

    def extract_segments(source, highlights, transcript, out_dir, **kw):
        calls["kw"] = kw
        calls["highlights"] = highlights
        path = os.path.join(out_dir, "video_clip_1.mp4")
        with open(path, "wb") as f:
            f.write(b"new video")
        return [path]

    def thumb(v, t, badge_text="", at_time=0):
        with open(t, "wb") as f:
            f.write(b"new thumb")
    video.extract_segments = extract_segments
    video.generate_thumbnail_with_badge = thumb
    monkeypatch.setitem(sys.modules, "engine.analysis", analysis)
    monkeypatch.setitem(sys.modules, "engine.video_gen", video)


def test_rerender_replaces_the_clip_keeps_the_old_one_and_undo_restores_the_numbers(tmp_path, monkeypatch):
    session = _session(tmp_path)
    calls = {}
    _fake_engine(monkeypatch, calls)
    monkeypatch.chdir(tmp_path)

    clip = rerender.rerender_clip(str(session), 1, start=6.0, end=12.0, caption_style="GLOW_BOX")
    assert (session / "video_clip_1.mp4").read_bytes() == b"new video"
    assert (session / "video_clip_1.previous.mp4").read_bytes() == b"old video"
    assert (session / "video_clip_1.jpg").read_bytes() == b"new thumb"
    assert calls["highlights"] == [{"start": 6.0, "end": 12.0}] and calls["kw"]["caption_style"] == "GLOW_BOX"
    assert calls["kw"]["use_remotion"] is True and calls["kw"]["silence_intervals"] == [(0, 4), (5, 12)]
    assert "analysed" not in calls                                    # 6-12 s is already covered by the cached interest points
    saved = json.loads((session / "results.json").read_text())["clips"][0]
    assert (saved["start"], saved["end"], saved["duration"], saved["caption_style"]) == (6.0, 12.0, 6.0, "GLOW_BOX")
    assert clip["previous"]["start"] == 5.0

    assert rerender.undo_rerender(str(session), 1) is True
    assert (session / "video_clip_1.mp4").read_bytes() == b"old video"
    back = json.loads((session / "results.json").read_text())["clips"][0]
    assert (back["start"], back["end"], back["duration"]) == (5.0, 14.0, 9.0)
    assert "previous" not in back and "caption_style" not in back     # the original clip had no style of its own
    assert rerender.undo_rerender(str(session), 1) is False            # nothing left to undo


def test_a_window_outside_the_analysed_range_is_analysed_on_demand(tmp_path, monkeypatch):
    session = _session(tmp_path)
    calls = {}
    _fake_engine(monkeypatch, calls)
    monkeypatch.chdir(tmp_path)
    rerender.rerender_clip(str(session), 1, start=40.0, end=60.0)
    assert calls["analysed"] == [(40.0, 60.0)]


@pytest.mark.parametrize("kwargs,reason", [({"clip_index": 9}, "no clip 9"), ({"clip_index": 1, "start": 5, "end": 6}, "at least")])
def test_bad_requests_get_a_plain_reason(tmp_path, monkeypatch, kwargs, reason):
    session = _session(tmp_path)
    _fake_engine(monkeypatch, {})
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match=reason):
        rerender.rerender_clip(str(session), **kwargs)


def test_missing_source_or_results_cannot_be_rerendered(tmp_path):
    session = _session(tmp_path, with_source=False)
    with pytest.raises(ValueError, match="original video"):
        rerender.rerender_clip(str(session), 1)
    with pytest.raises(ValueError, match="no results.json"):
        rerender.rerender_clip(str(tmp_path / "empty"), 1)


def test_rerender_keeps_hook_overlay_and_clean_audio_from_the_original_run(tmp_path, monkeypatch):
    session = _session(tmp_path)
    data = json.loads((session / "results.json").read_text())
    data["settings"].update({"hook_overlay": True, "clean_audio": True})
    data["clips"][0]["hook"] = "Save money on unused subscriptions"
    (session / "results.json").write_text(json.dumps(data))
    calls = {}
    _fake_engine(monkeypatch, calls)

    def extract_with_env(source, highlights, transcript, out_dir, **kw):
        calls["hook_env"] = os.environ.get("SHORTSFLOW_HOOK_OVERLAY")
        calls["highlights"] = highlights
        path = os.path.join(out_dir, "video_clip_1.mp4")
        with open(path, "wb") as f:
            f.write(b"new video")
        return [path]
    sys.modules["engine.video_gen"].extract_segments = extract_with_env
    cleaned = []
    audio = types.ModuleType("engine.audio_clean")
    audio.clean_audio = lambda p, **kw: cleaned.append(os.path.basename(p)) or True
    monkeypatch.setitem(sys.modules, "engine.audio_clean", audio)
    monkeypatch.delenv("SHORTSFLOW_HOOK_OVERLAY", raising=False)
    monkeypatch.chdir(tmp_path)

    rerender.rerender_clip(str(session), 1, start=6.0, end=12.0)
    assert calls["hook_env"] == "1"                                   # the title is drawn again
    assert calls["highlights"][0]["hook_text"] == "Save money on unused subscriptions"
    assert cleaned == ["video_clip_1.mp4"]                            # and the sound is cleaned again
    assert "SHORTSFLOW_HOOK_OVERLAY" not in os.environ                # nothing leaks into later in-process renders


def test_cli_survives_a_cp1252_console(monkeypatch):
    """Progress lines contain emoji; a redirected Windows console (cp1252) must not turn them into a failed re-render."""
    import io
    import sys

    from engine import rerender

    raw = io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", out)
    rerender._utf8_console()
    print("[Log] NVIDIA GPU Detected \U0001f680")
    out.flush()
    assert "\U0001f680".encode("utf-8") in raw.getvalue()
