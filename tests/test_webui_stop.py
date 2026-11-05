import json
import os
import subprocess
import sys
import time

import pytest

gr = pytest.importorskip("gradio")
import webui  # noqa: E402


def test_stop_button_ends_a_running_pipeline_and_says_so():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    webui._JOBS.append(proc)
    try:
        msg = webui.stop_jobs()
        for _ in range(50):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        assert proc.poll() is not None, "the process was not ended"
        assert proc.pid in webui._STOPPED and msg.startswith("⏹ Stopped") and "Continue one that stopped" in msg
    finally:
        if proc.poll() is None:
            proc.kill()
        if proc in webui._JOBS:
            webui._JOBS.remove(proc)
    assert webui.stop_jobs() == "Nothing is running right now."


def test_a_stopped_run_is_reported_as_stopped_not_failed(monkeypatch):
    # _run reports "Stopped" for a process the Stop button ended
    script = "import time\nprint('working', flush=True)\ntime.sleep(60)"
    monkeypatch.setattr(webui, "_pipeline_cmd", lambda: [sys.executable, "-u", "-c", script])
    gen = webui._run([sys.executable, "-u", "-c", script])
    logs = []
    for log, _videos in gen:
        logs.append(log)
        if "working" in log:
            webui.stop_jobs()
    assert "⏹ Stopped" in logs[-1] and "exited with code" not in logs[-1]


def _session(tmp_path, name, cmd, results=False):
    d = tmp_path / "sessions" / name
    d.mkdir(parents=True)
    webui.save_command(str(d), cmd)
    if results:
        (d / "results.json").write_text("{}")
    return d


def test_unfinished_runs_lists_only_runs_without_results(tmp_path):
    _session(tmp_path, "web_20261104_204742", ["py", "main.py", "--source_video", "F:/v/clip.mp4"])
    _session(tmp_path, "web_20261104_190000", ["py", "main.py", "--source_video", "F:/v/done.mp4"], results=True)
    (tmp_path / "sessions" / "web_20261104_180000").mkdir()                                        # no saved command: not listed
    runs = webui.unfinished_runs(str(tmp_path))
    assert [label for label, _ in runs] == ["04.11.2026 20:47 - clip.mp4"]
    assert runs[0][1].endswith("command.json")


def test_continue_reuses_the_same_folder_with_the_cache(tmp_path, monkeypatch):
    video = tmp_path / "src.mp4"
    video.write_bytes(b"x")
    d = _session(tmp_path, "web_20261104_204742", ["py", "main.py", "--source_video", str(video), "--extract_mode", "shorts",
                                                    "--find", "pricing", "--session_dir", "S", "--output_json", "R"])
    seen = {}
    monkeypatch.setattr(webui, "_stream_clip", lambda cmd, results, long_form, minutes, find: iter([seen.update(
        cmd=cmd, results=results, long_form=long_form, find=find) or ("ok", "", [])]))
    out = list(webui.continue_run(str(d / "command.json")))
    assert out and "--use_cache" in seen["cmd"] and seen["cmd"].count("--use_cache") == 1
    assert seen["results"] == str(d / "results.json") and seen["long_form"] is False and seen["find"] == "pricing"


def test_continue_explains_a_missing_video_and_an_empty_choice(tmp_path):
    d = _session(tmp_path, "web_20261104_204742", ["py", "main.py", "--source_video", str(tmp_path / "gone.mp4")])
    with pytest.raises(gr.Error, match="no longer where it was"):
        list(webui.continue_run(str(d / "command.json")))
    with pytest.raises(gr.Error, match="Pick an unfinished run"):
        list(webui.continue_run(None))
    (d / "command.json").write_text("not json")
    with pytest.raises(gr.Error, match="could not be read"):
        list(webui.continue_run(str(d / "command.json")))


def test_ui_has_a_stop_button_on_every_tab():
    demo = webui.build_ui()
    labels = [getattr(b, "value", None) for b in demo.blocks.values() if type(b).__name__ == "Button"]
    assert labels.count("⏹ Stop") == 6
    assert "Continue" in labels


def test_length_of_each_short_reaches_the_command(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(webui, "ROOT", str(tmp_path))
    monkeypatch.setattr(webui, "save_command", lambda session, cmd: None)
    monkeypatch.setattr(webui, "_stream_clip", lambda cmd, results, lf, minutes, find: iter([seen.update(cmd=cmd) or ("ok", "", [])]))
    list(webui.quick_clip("a.mp4", None, 3, False, length=45))
    cmd = seen["cmd"]
    assert cmd[cmd.index("--target_duration") + 1] == "45" and cmd[cmd.index("--min_duration") + 1] == "27"
    list(webui.quick_clip("a.mp4", None, 3, False, length=15))
    cmd = seen["cmd"]
    assert cmd[cmd.index("--target_duration") + 1] == "15" and cmd[cmd.index("--min_duration") + 1] == "9"


def test_length_is_kept_inside_what_a_short_can_be():
    assert webui._length(30) == 30 and webui._length(200) == 60 and webui._length(3) == 10
    assert webui._length(None) == 30 and webui._length("abc") == 30 and webui._length(22.7) == 22


def test_exact_times_reach_the_command_and_typos_are_reported_early(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(webui, "ROOT", str(tmp_path))
    monkeypatch.setattr(webui, "save_command", lambda session, cmd: None)
    monkeypatch.setattr(webui, "_stream_clip", lambda cmd, results, lf, minutes, find: iter([seen.update(cmd=cmd) or ("ok", "", [])]))
    list(webui.quick_clip("a.mp4", None, 3, False, moments="7:00-7:45\n61:40-62:30"))
    assert seen["cmd"][seen["cmd"].index("--moments") + 1] == "7:00-7:45\n61:40-62:30"
    list(webui.quick_clip("a.mp4", None, 3, False))
    assert "--moments" not in seen["cmd"]
    with pytest.raises(gr.Error, match="Exact times: .* not a time"):
        list(webui.quick_clip("a.mp4", None, 3, False, moments="seven o'clock"))
