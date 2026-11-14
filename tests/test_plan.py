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


def test_framing_from_command():
    f = plan.framing_from_command
    assert f(["main.py", "--layout", "single", "--game_framing", "crop"]) == ("crop", "9:16")
    assert f(["main.py", "--layout", "fit"]) == ("fit", "9:16")
    assert f(["main.py", "--layout", "single", "--game_framing", "fit"]) == ("fit", "9:16")
    assert f(["main.py", "--extract_mode", "long"]) == (None, "9:16")
    assert f(["main.py", "--aspect_ratio", "16:9"]) == (None, "16:9")
    assert f(["main.py", "--aspect_ratio", "1:1"]) == ("crop", "1:1")
    assert f(None) == ("crop", "9:16")


def test_preview_has_the_shape_of_the_short(tmp_path):
    import shutil
    import subprocess
    import pytest
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("no ffmpeg")
    src = tmp_path / "in.mp4"
    subprocess.run([exe, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=640x360:d=3", "-f", "lavfi", "-i", "sine=d=3",
                    "-shortest", "-c:v", "libx264", str(src)], check=True)
    for framing in ("crop", "fit"):
        out = plan.make_preview(str(src), 0, 2, str(tmp_path / f"{framing}.mp4"), framing=framing)
        size = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", out]).decode().split()[0]
        assert size == "270,480", framing
    out = plan.make_preview(str(src), 0, 2, str(tmp_path / "full.mp4"))
    size = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", out]).decode().split()[0]
    assert size.endswith(",360")


def test_automatic_game_framing_uses_the_tools_decision_once(tmp_path):
    calls = []

    def fake_choose(video, moments):
        calls.append(len(moments))
        return "fit", "2 of 6 moments have a HUD or subtitles at the sides"
    cmd = ["main.py", "--content", "game", "--layout", "single"]
    moments = [{"start": 10, "end": 40}, {"start": 50, "end": 80}]
    first = plan.automatic_game_framing(cmd, "v.mp4", moments, str(tmp_path), choose=fake_choose)
    assert first[0] == "fit" and "HUD" in first[1]
    second = plan.automatic_game_framing(cmd, "v.mp4", moments, str(tmp_path), choose=fake_choose)
    assert second == first and calls == [2]                       # looked at once, kept for the render


def test_automatic_game_framing_leaves_explicit_choices_and_other_footage_alone(tmp_path):
    never = lambda *a: (_ for _ in ()).throw(AssertionError("should not look"))
    m = [{"start": 1, "end": 31}]
    assert plan.automatic_game_framing(["--content", "game", "--game_framing", "crop"], "v", m, str(tmp_path), choose=never) is None
    assert plan.automatic_game_framing(["--content", "game", "--layout", "fit"], "v", m, str(tmp_path), choose=never) is None
    assert plan.automatic_game_framing(["--layout", "single"], "v", m, str(tmp_path), choose=never) is None


def test_a_failed_look_falls_back_to_a_crop_preview(tmp_path):
    def broken(video, moments):
        raise RuntimeError("no frames")
    out = plan.automatic_game_framing(["--content", "game"], "v", [{"start": 1, "end": 31}], str(tmp_path), choose=broken)
    assert out[0] == "crop" and "could not look" in out[1]


def test_recap_handwritten_font_choice():
    from engine import trip_recap as tr
    tr.set_text_font("handwritten")
    try:
        assert tr._text_font_file("Kaindy Lake") == ("Caveat.ttf", 1.3)
        assert tr._text_font_file("Привет")[0] == "Caveat.ttf"          # Caveat has Cyrillic
        assert tr._text_font_file("مرحبا")[0] != "Caveat.ttf"           # scripts without glyphs keep the normal font
        assert tr._text_font_file("你好")[0] != "Caveat.ttf"
        tr.set_text_font("nonsense")
        assert tr.TEXT_FONT["name"] == "default"
    finally:
        tr.set_text_font("default")
    assert tr._text_font_file("Kaindy Lake") == ("Anton-Regular.ttf", 1.0)


def test_handwritten_recap_reaches_the_command_and_the_cli():
    import os
    from shortsflow import web_args
    assert web_args.trip_args(["a.mp4"], "s")[:2] == ["--mode", "TRIP"]
    assert "--recap_font" not in web_args.trip_args(["a.mp4"], "s")
    args = web_args.trip_args(["a.mp4"], "s", font="handwritten")
    assert args[args.index("--recap_font") + 1] == "handwritten"
    src = open(os.path.join(os.path.dirname(__file__), "..", "shortsflow", "_main.py"), encoding="utf-8").read()
    assert '"--recap_font", choices=["default", "handwritten"]' in src


def test_template_pieces_go_on_every_finished_recap():
    from engine import trip_recap as tr
    seen = []
    props = {"visualTemplate": "story-progress"}
    n = tr.apply_template_to_recaps(["a.mp4", "b.mp4"], props, apply=lambda v, p: seen.append(v) or True)
    assert n == 2 and seen == ["a.mp4", "b.mp4"]
    assert tr.apply_template_to_recaps(["a.mp4"], {}, apply=lambda v, p: 1 / 0) == 0          # nothing chosen: nothing drawn


def test_a_failing_template_never_loses_a_recap():
    from engine import trip_recap as tr

    def boom(video, props):
        raise RuntimeError("renderer missing")
    assert tr.apply_template_to_recaps(["a.mp4"], {"introAnimation": "tiles"}, apply=boom) == 0


def test_the_recap_form_passes_the_template_to_the_command():
    from shortsflow import web_args
    a = web_args.template_args("story-progress", "iris", "fade", show="Almaty")
    assert a[a.index("--visual_template") + 1] == "story-progress" and "show=Almaty" in a
    assert a[a.index("--intro_animation") + 1] == "iris"
