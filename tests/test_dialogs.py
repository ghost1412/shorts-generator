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


def test_mode_cards_have_an_icon_and_a_description_for_every_mode():
    from shortsflow.ui import theme
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    import re
    labels = re.search(r"def web_args_modes\(\):.*?return \[(.*?)\]\n", src, re.S).group(1)
    for label in re.findall(r'\("([^"]+)", "[a-z]+"\)', labels):
        assert any(label == m[0] for m in theme.MODES), f"no card style for the mode {label!r}"
    css = theme.mode_card_css()
    assert css.count("::before { -webkit-mask-image") == len(theme.MODES) and css.count("::after { content:") == len(theme.MODES)
    assert 'elem_id="sf-modes"' in src


def test_galleries_are_responsive_so_a_phone_does_not_scroll_sideways():
    import os
    root = os.path.join(os.path.dirname(__file__), "..")
    web = open(os.path.join(root, "webui.py"), encoding="utf-8").read()
    blocks = open(os.path.join(root, "shortsflow", "ui", "blocks.py"), encoding="utf-8").read()
    assert "columns=4" not in web and "columns=5" not in blocks          # fixed column counts forced a 544 px wide page on a 390 px phone
    assert "columns=[2, 2, 3, 4, 4, 4]" in web and "columns=[2, 3, 4, 5, 5, 5]" in blocks
