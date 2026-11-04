import json
import os

import pytest

from shortsflow import batch
from shortsflow.cli import clip_args, clip_plan


def _touch(path, size=10):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * size)
    return str(path)


def test_collect_videos_expands_folders_keeps_links_and_reports_problems(tmp_path):
    a = _touch(tmp_path / "in" / "b.mp4")
    _touch(tmp_path / "in" / "a.MOV")
    _touch(tmp_path / "in" / "notes.txt")
    _touch(tmp_path / "in" / ".hidden.mp4")
    _touch(tmp_path / "in" / "sub" / "deep.mp4")
    (tmp_path / "empty").mkdir()
    sources, problems = batch.collect_videos([str(tmp_path / "in"), a, "https://youtu.be/abc", str(tmp_path / "empty"),
                                              str(tmp_path / "missing.mp4")])
    names = [s if s.startswith("http") else os.path.basename(s) for s in sources]
    assert names == ["a.MOV", "b.mp4", "https://youtu.be/abc"]  # sorted, no sub-folders, hidden/other files skipped, b.mp4 once
    assert any("empty" in p and "No video" in p for p in problems)
    assert any("missing.mp4" in p and "not found" in p for p in problems)


def test_safe_stem_and_session_names_are_unique_and_folder_safe():
    assert batch.safe_stem("C:/v/My Talk (final).mp4") == "My_Talk__final"
    assert batch.safe_stem("https://www.youtube.com/watch?v=abc") == "watch_v_abc"
    s1, s2 = batch.session_for("a.mp4", 1, "20260101_000000"), batch.session_for("a.mp4", 2, "20260101_000000")
    assert s1 != s2 and s1.startswith(os.path.join("sessions", "batch_20260101_000000_01"))


def test_item_flags_add_session_results_and_a_default_report():
    flags = batch.item_flags(["--clip_count", "2"], "a.mp4", os.path.join("sessions", "s1"))
    assert flags[:2] == ["--source_video", "a.mp4"]
    assert flags[flags.index("--session_dir") + 1] == os.path.join("sessions", "s1")
    assert flags[flags.index("--output_json") + 1] == os.path.join("sessions", "s1", "results.json")
    assert flags[flags.index("--clip_report") + 1] == "md"
    own = batch.item_flags(["--clip_report", "csv"], "a.mp4", "s")
    assert own.count("--clip_report") == 1 and own[own.index("--clip_report") + 1] == "csv"


def test_run_batch_continues_past_failures_and_summarises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = ["a.mp4", "b.mp4", "c.mp4", "d.mp4"]
    calls = []

    def runner(flags):
        src = flags[flags.index("--source_video") + 1]
        calls.append(src)
        session = flags[flags.index("--session_dir") + 1]
        if src == "b.mp4":
            return 1                                  # pipeline failed
        if src == "c.mp4":
            raise OSError("cannot start")             # even a child that cannot start must not stop the batch
        os.makedirs(session, exist_ok=True)
        clips = [{"clip_index": i} for i in range(2 if src == "a.mp4" else 0)]
        with open(os.path.join(session, "results.json"), "w", encoding="utf-8") as f:
            json.dump({"clips": clips}, f)
        return 0

    lines = []
    results = batch.run_batch(sources, ["--clip_count", "2"], runner=runner, out=lines.append)
    assert calls == sources
    assert [(r["status"], r["clips"]) for r in results] == [("ok", 2), ("failed", 0), ("failed", 0), ("no clips", 0)]
    table = batch.summary_table(results)
    assert "a.mp4" in table and "failed" in table and "no clips" in table
    assert "4 video(s), 2 short(s), 2 failed." in table
    assert any("cannot start" in line for line in lines)


def test_watch_waits_for_a_stable_file_and_processes_each_file_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "inbox"
    video = _touch(folder / "new.mp4", 10)
    ran = []

    def runner(flags):
        ran.append(flags[flags.index("--source_video") + 1])
        return 0

    state = batch.state_path(str(folder))
    pending = {}
    assert batch.watch_once(str(folder), [], state, pending, runner, out=lambda *_: None) == []  # first sighting: wait
    with open(video, "ab") as f:
        f.write(b"more")                                                                       # still being copied
    assert batch.watch_once(str(folder), [], state, pending, runner, out=lambda *_: None) == []
    os.utime(video, (1_800_000_000, 1_800_000_000))                                            # changed once more
    assert batch.watch_once(str(folder), [], state, pending, runner, out=lambda *_: None) == []
    res = batch.watch_once(  # same fingerprint as the poll before: the copy is finished, so it runs now
str(folder), [], state, pending, runner, out=lambda *_: None)
    assert len(res) == 1 and ran == [video]
    assert batch.watch_once(str(folder), [], state, pending, runner, out=lambda *_: None) == []   # never again
    assert batch.load_done(state)[os.path.abspath(video)]["status"] in ("ok", "no clips")
    # a second watcher run (fresh `pending`) still remembers it
    pending2 = {}
    for _ in range(3):
        assert batch.watch_once(str(folder), [], state, pending2, runner, out=lambda *_: None) == []
    assert ran == [video]
    # a brand new file is picked up on its own
    video2 = _touch(folder / "second.mp4", 5)
    for _ in range(3):
        batch.watch_once(str(folder), [], state, pending2, runner, out=lambda *_: None)
    assert ran == [video, video2]


def test_watch_loop_stops_on_ctrl_c_and_sleeps_between_polls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "inbox"
    folder.mkdir()
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:
            raise KeyboardInterrupt

    lines = []
    out = batch.watch(str(folder), [], interval=7, runner=lambda f: 0, out=lines.append, sleep=sleep)
    assert out == [] and slept == [7, 7]
    assert any("Stopped watching" in line for line in lines)


def test_clip_args_single_video_is_unchanged_and_several_need_the_batch_path():
    flags = clip_args(["talk.mp4", "--count", "5", "--captions"])
    assert flags[:2] == ["--source_video", "talk.mp4"] and "--use_remotion" in flags and flags[flags.index("--clip_count") + 1] == "5"
    with pytest.raises(SystemExit):
        clip_args(["a.mp4", "b.mp4"])


def test_clip_plan_kinds_and_path_resolution(tmp_path):
    _touch(tmp_path / "v" / "a.mp4")
    _touch(tmp_path / "v" / "b.mp4")
    single = clip_plan(["a.mp4"], base_dir=str(tmp_path / "v"))
    assert single["kind"] == "single" and single["flags"][1] == str(tmp_path / "v" / "a.mp4")
    many = clip_plan(["a.mp4", "b.mp4", "--count", "2"], base_dir=str(tmp_path / "v"))
    assert many["kind"] == "batch" and len(many["sources"]) == 2 and "--source_video" not in many["flags"]
    folder = clip_plan(["v"], base_dir=str(tmp_path))
    assert folder["kind"] == "batch" and [os.path.basename(s) for s in folder["sources"]] == ["a.mp4", "b.mp4"]
    link = clip_plan(["https://youtu.be/x"])
    assert link["kind"] == "single" and link["flags"][1] == "https://youtu.be/x"
    watch = clip_plan(["--watch", "v", "--interval", "1"], base_dir=str(tmp_path))
    assert watch["kind"] == "watch" and watch["folder"] == str(tmp_path / "v") and watch["interval"] == 5  # floor of 5 s
    assert clip_plan(["--watch", "nope"], base_dir=str(tmp_path))["problems"]
    with pytest.raises(SystemExit):
        clip_plan([])
