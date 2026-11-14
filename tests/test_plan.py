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


def test_make_preview_rejects_bad_input_and_leaves_source_alone(tmp_path):
    assert plan.make_preview(str(tmp_path / "missing.mp4"), 1, 5, str(tmp_path / "p.mp4")) is None
    src = tmp_path / "s.txt"
    src.write_text("x")
    assert plan.make_preview(str(src), 5, 1, str(tmp_path / "p.mp4")) is None
    assert plan.make_preview(str(src), "a", 1, str(tmp_path / "p.mp4")) is None
    assert src.read_text() == "x"


def test_make_preview_cuts_a_real_clip(tmp_path):
    import shutil
    import subprocess
    import pytest
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("no ffmpeg")
    src = tmp_path / "in.mp4"
    subprocess.run([exe, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=320x240:d=4", "-f", "lavfi", "-i", "sine=d=4",
                    "-shortest", "-c:v", "libx264", str(src)], check=True)
    out = plan.make_preview(str(src), 1, 3, str(tmp_path / "sub" / "p.mp4"), height=120)
    assert out and (tmp_path / "sub" / "p.mp4").stat().st_size > 0
