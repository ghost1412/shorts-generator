from engine import feedback


def _entries(spec):
    return [{"title": "t", "duration": d, "score": 70, "liked": liked} for d, liked in spec]


def test_no_preference_until_enough_clear_ratings():
    assert feedback.preferred_duration([]) is None
    assert feedback.preferred_duration(_entries([(30, True)] * 4)) is None                           # nothing disliked
    few = _entries([(30, True), (30, True), (30, True), (50, False), (50, False)])
    assert feedback.preferred_duration(few) is None                                                  # fewer than 8 ratings
    same = _entries([(40, True)] * 4 + [(41, False)] * 4)
    assert feedback.preferred_duration(same) is None                                                 # liked and disliked look alike


def test_preferred_length_is_the_average_of_the_liked_clips():
    e = _entries([(28, True), (30, True), (32, True), (31, True), (52, False), (55, False), (49, False), (58, False)])
    assert feedback.preferred_duration(e) == 30.2


def test_nudge_is_small_and_peaks_at_the_preferred_length():
    assert feedback.nudge(30, 30) == 5.0 and feedback.nudge(30, None) == 0.0 and feedback.nudge(0, 30) == 0.0
    assert feedback.nudge(31, 30) > feedback.nudge(40, 30) > feedback.nudge(59, 30)
    assert -5.0 <= feedback.nudge(59, 30) <= feedback.nudge(30, 30) <= 5.0


def test_preferences_reorder_close_calls_but_not_clear_winners(monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_NO_FEEDBACK", raising=False)
    entries = _entries([(28, True), (30, True), (32, True), (31, True), (52, False), (55, False), (49, False), (58, False)])
    hl = [{"start": 0, "end": 55, "final_score": 80.0}, {"start": 100, "end": 130, "final_score": 78.5},
          {"start": 200, "end": 255, "final_score": 60.0}]
    out = feedback.apply_preferences(hl, entries)
    assert out[1]["final_score"] > out[0]["final_score"]                       # the 30 s clip now edges out the 55 s clip
    assert out[2]["final_score"] < out[1]["final_score"]                       # a clearly weaker clip stays behind
    assert hl[0]["final_score"] == 80.0 and "feedback_nudge" not in hl[0]      # inputs are not modified
    assert feedback.apply_preferences(hl, []) is hl                            # no preference yet: untouched
    monkeypatch.setenv("SHORTSFLOW_NO_FEEDBACK", "1")
    assert feedback.apply_preferences(hl, entries) is hl


def test_record_load_roundtrip_and_summary(tmp_path):
    path = str(tmp_path / "sub" / "feedback.json")
    assert feedback.load(path) == []
    assert feedback.record("Clip A", 31.234, 77, True, path) == 1
    assert feedback.record("Clip B", 50, None, False, path) == 2
    got = feedback.load(path)
    assert [e["liked"] for e in got] == [True, False] and got[0]["duration"] == 31.2 and got[1]["score"] is None
    assert "2 ratings saved (1 liked)" in feedback.summary(got) and "Rate at least 8" in feedback.summary(got)
    assert feedback.summary([]) == "No ratings yet."
    (tmp_path / "bad.json").write_text("{not json")
    assert feedback.load(str(tmp_path / "bad.json")) == []


def test_rate_clip_handler_saves_and_explains(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("gradio")
    monkeypatch.setenv("SHORTSFLOW_CACHE", str(tmp_path))
    import webui
    msg = webui.rate_clip({"title": "A clip", "duration": 33.0, "score": 80}, True)
    assert msg.startswith("Thanks!") and "1 rating saved (1 liked)" in msg
    assert webui.rate_clip({"title": "B", "duration": 50, "score": None}, False).startswith("Noted.")
    assert len(feedback.load()) == 2
