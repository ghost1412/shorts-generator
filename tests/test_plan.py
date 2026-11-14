from engine import plan


def test_write_read_roundtrip(tmp_path):
    hs = [{"start": 10.0, "end": 40.5, "title": "A", "final_score": 80, "reason": "r"}, {"start": 100, "end": 130, "hook": "B"}]
    path = plan.write_plan(str(tmp_path), hs, "v.mp4")
    assert path.endswith("plan.json")
    data = plan.read_plan(str(tmp_path))
    assert data["source_video"] == "v.mp4"
    assert [m["title"] for m in data["moments"]] == ["A", "B"]
    assert data["moments"][0]["score"] == 80 and data["moments"][1]["index"] == 2


def test_read_plan_missing_or_bad(tmp_path):
    assert plan.read_plan(str(tmp_path)) is None
    (tmp_path / "plan.json").write_text("{nope", encoding="utf-8")
    assert plan.read_plan(str(tmp_path)) is None


def test_moments_text_sorted_and_parseable():
    from engine.moments import parse_moments
    text = plan.moments_text([{"start": 600, "end": 640}, {"start": 420.5, "end": 465}])
    assert text == "420.50-465.00, 600.00-640.00"
    assert [m["start"] for m in parse_moments(text)] == [420.5, 600.0]


def test_only_between_window():
    import pytest
    from engine.modes.clip_extract import _window
    assert _window("30:00-60:00") == (1800.0, 3600.0)
    assert _window("") is None and _window(None) is None
    with pytest.raises(SystemExit):
        _window("60:00-30:00")
    with pytest.raises(SystemExit):
        _window("nonsense")
