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
