import os
import sys

import pytest


def test_webui_runs_main_py_in_a_checkout_and_the_module_in_a_pip_install(monkeypatch, tmp_path):
    pytest.importorskip("gradio")
    import webui
    monkeypatch.setattr(webui, "ROOT", str(tmp_path))
    assert webui._pipeline_cmd() == [sys.executable, "-m", "shortsflow"]
    (tmp_path / "main.py").write_text("")
    assert webui._pipeline_cmd() == [sys.executable, "main.py"]


def test_cli_webui_without_gradio_explains_what_to_install(monkeypatch, capsys):
    from shortsflow import cli
    monkeypatch.setitem(sys.modules, "gradio", None)   # makes `import gradio` raise ImportError
    monkeypatch.setattr(cli.workspace, "bootstrap", lambda: os.getcwd())
    with pytest.raises(SystemExit):
        cli.main(["webui"])
    assert 'shortsflow[webui]' in capsys.readouterr().out


def test_missing_ffprobe_does_not_break_the_video_player(monkeypatch):
    pytest.importorskip("gradio")
    import webui
    from gradio import processing_utils
    original = processing_utils.video_is_playable
    try:
        monkeypatch.setattr(webui.shutil, "which", lambda name: None)
        assert webui.tolerate_missing_ffprobe() is True
        assert processing_utils.video_is_playable("anything.mp4") is True
        monkeypatch.setattr(webui.shutil, "which", lambda name: "/usr/bin/ffprobe")
        processing_utils.video_is_playable = original
        assert webui.tolerate_missing_ffprobe() is False and processing_utils.video_is_playable is original
    finally:
        processing_utils.video_is_playable = original


def test_quick_clip_applies_the_brand_typed_in_the_form_even_if_save_was_not_pressed(monkeypatch, tmp_path):
    pytest.importorskip("gradio")
    import webui
    from shortsflow import brand
    monkeypatch.setattr(webui, "ROOT", str(tmp_path))
    seen = {}

    def fake_run(cmd):
        seen["cmd"] = cmd
        yield "", []
    monkeypatch.setattr(webui, "_run", fake_run)
    list(webui.quick_clip("https://example.com/v", None, 2, False, "HORMOZI", True,
                          logo=None, handle="mychannel", end_card="", color="#FFEA00", position="top-right"))
    assert brand.load(str(tmp_path))["handle"] == "@mychannel"
    assert "--brand" in seen["cmd"]
    # brand switched off: nothing is saved or applied
    seen.clear()
    list(webui.quick_clip("https://example.com/v", None, 2, False, "HORMOZI", False, handle="other"))
    assert "--brand" not in seen["cmd"]
    assert brand.load(str(tmp_path))["handle"] == "@mychannel"


def test_quick_clip_highlights_video_uses_long_mode_and_shows_the_reel(monkeypatch, tmp_path):
    pytest.importorskip("gradio")
    import webui
    monkeypatch.setattr(webui, "ROOT", str(tmp_path))
    seen = {}

    def fake_run(cmd):
        seen["cmd"] = cmd
        yield "", [str(tmp_path / "highlight_reel.mp4")]
    monkeypatch.setattr(webui, "_run", fake_run)
    out = list(webui.quick_clip("https://example.com/v", None, 3, True, "HORMOZI", True, handle="x", mode="long", minutes=3))
    cmd = seen["cmd"]
    assert cmd[cmd.index("--extract_mode") + 1] == "long"
    assert cmd[cmd.index("--target_duration") + 1] == "180"
    assert "--reel_captions" in cmd and "--smart_crop" not in cmd and "--brand" not in cmd
    status, _, cards = out[-1]
    assert status.startswith("✅") and cards[0]["title"] == "Highlights video"
