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
