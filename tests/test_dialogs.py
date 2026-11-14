import json
import subprocess

from shortsflow.ui import dialogs


class _Result:
    def __init__(self, out):
        self.stdout = out


def test_script_is_valid_python():
    compile(dialogs._SCRIPT, "dialog", "exec")


def test_pick_returns_the_chosen_paths_and_passes_the_kind():
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return _Result("noise on the first line\n" + json.dumps(["C:/a/day1", "C:/a/day2"]) + "\n")
    got = dialogs.pick("folder", "Choose a folder", run=fake_run)
    assert got == ["C:/a/day1", "C:/a/day2"]
    assert seen["cmd"][3] == "folder" and seen["cmd"][4] == "Choose a folder"


def test_cancel_or_failure_gives_no_paths():
    assert dialogs.pick("file", run=lambda cmd, **kw: _Result("[]")) == []
    assert dialogs.pick("file", run=lambda cmd, **kw: _Result("")) == []
    assert dialogs.pick("file", run=lambda cmd, **kw: _Result("not json")) == []

    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    assert dialogs.pick("file", run=boom) == []
    assert dialogs.pick("file", run=lambda cmd, **kw: _Result(json.dumps([1, None, ""]))) == []


def test_available_follows_the_environment():
    assert dialogs.available(env={"SHORTSFLOW_NO_DIALOG": "1"}, platform="win32") is False
    assert dialogs.available(env={"SHORTSFLOW_DOCKER": "1"}, platform="win32") is False
    assert dialogs.available(env={}, platform="linux") is False                 # no desktop session
    # a desktop session on Windows works when tkinter is installed (it is part of the standard Python installer)
    import importlib.util
    has_tk = importlib.util.find_spec("tkinter") is not None
    assert dialogs.available(env={}, platform="win32") == has_tk


def test_append_line_adds_without_duplicates():
    assert dialogs.append_line("a\n\n b ", ["b", "c"]) == "a\nb\nc"
    assert dialogs.append_line("", ["x"]) == "x"
    assert dialogs.append_line("a", []) == "a"
    assert dialogs.append_line(None, None) == ""
