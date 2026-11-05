"""Reuse an earlier run's slow results (transcript, moments, picture descriptions, cut pieces) in a new run from the browser app."""
import json
import os

import pytest

from shortsflow import reuse


def make_run(root, name, cmd, files=(), segments=()):
    d = os.path.join(root, "sessions", name)
    os.makedirs(os.path.join(d, "temp_segments"), exist_ok=True)
    with open(os.path.join(d, "command.json"), "w", encoding="utf-8") as f:
        json.dump({"cmd": cmd}, f)
    for n in files:
        with open(os.path.join(d, n), "w", encoding="utf-8") as f:
            f.write(json.dumps({"name": n}))
    for n in segments:
        with open(os.path.join(d, "temp_segments", n), "wb") as f:
            f.write(b"x" * 2000)
    return d


def test_earlier_runs_lists_finished_and_unfinished_clip_runs(tmp_path):
    root = str(tmp_path)
    done = make_run(root, "web_20261104_204742", ["py", "--source_video", "C:/v/game.mp4", "--extract_mode", "shorts"], ["results.json"])
    make_run(root, "web_20261105_101500", ["py", "--source_video", "https://youtu.be/abc", "--skip-upload"])
    make_run(root, "trip_20261105_090000", ["py", "--mode", "TRIP", "--trip_videos", "a.mp4"])
    (tmp_path / "sessions" / "web_20261101_000000").mkdir()                       # no command.json: not reusable
    rows = reuse.earlier_runs(root, "clip")
    assert [os.path.basename(os.path.dirname(p)) for _, p in rows] == ["web_20261105_101500", "web_20261104_204742"]
    assert rows[0][0].endswith("abc (unfinished)") and rows[1][0].endswith("game.mp4") and "04.11.2026 20:47" in rows[1][0]
    assert reuse.source_of(os.path.join(done, "command.json")) == "C:/v/game.mp4"


def test_earlier_trip_runs_use_the_trip_name_and_videos(tmp_path):
    root = str(tmp_path)
    cmd = ["py", "--mode", "TRIP", "--trip_videos", "C:/a/day1", "C:/a/day2", "--session_dir", "s", "--trip_name", "Almaty trip"]
    d = make_run(root, "trip_20261105_090000", cmd, ["recap.mp4"])
    rows = reuse.earlier_runs(root, "trip")
    assert len(rows) == 1 and rows[0][0].endswith("Almaty trip")
    assert reuse.trip_videos_of(os.path.join(d, "command.json")) == ["C:/a/day1", "C:/a/day2"]


def test_seed_session_copies_the_slow_results_but_never_the_finished_clips(tmp_path):
    old = make_run(str(tmp_path), "web_a", ["py"], ["transcript.json", "visual_context.json", "highlights.json", "interest_points.json",
                                                      "silence_intervals.json", "results.json", "video_clip_1.mp4"], ["seg_0.mp4", "seg_1.part.mp4", "notes.txt"])
    new = str(tmp_path / "new")
    got = sorted(reuse.seed_session(old, new, keep_moments=True))
    assert got == sorted(["transcript.json", "visual_context.json", "highlights.json", "interest_points.json", "silence_intervals.json",
                          os.path.join("temp_segments", "seg_0.mp4")])
    assert not os.path.exists(os.path.join(new, "results.json")) and not os.path.exists(os.path.join(new, "video_clip_1.mp4"))
    # without keeping the moments: only the transcript and the picture descriptions
    new2 = str(tmp_path / "new2")
    assert sorted(reuse.seed_session(old, new2, keep_moments=False)) == ["transcript.json", "visual_context.json"]
    # editing the copy must not change the earlier run
    with open(os.path.join(new, "transcript.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    assert json.load(open(os.path.join(old, "transcript.json"), encoding="utf-8")) == {"name": "transcript.json"}


def test_seed_trip_session_takes_descriptions_and_places_from_the_run_and_its_versions(tmp_path):
    old = make_run(str(tmp_path), "trip_a", ["py"], ["visual_context.json", "places.json", "recap.mp4"])
    sub = os.path.join(old, "portrait")
    os.makedirs(sub)
    with open(os.path.join(sub, "places.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    got = sorted(reuse.seed_session(old, str(tmp_path / "n"), kind="trip"))
    assert got == ["places.json", os.path.join("portrait", "places.json"), "visual_context.json"]


gr = pytest.importorskip("gradio")
import webui  # noqa: E402


def test_quick_clip_with_an_earlier_run_reuses_its_video_and_cache(tmp_path, monkeypatch):
    root = str(tmp_path)
    old = make_run(root, "web_20261104_204742", ["py", "--source_video", "C:/v/game.mp4"], ["transcript.json", "highlights.json"], ["seg_0.mp4"])
    monkeypatch.setattr(webui, "ROOT", root)
    seen = {}

    def fake_stream(cmd, results, long_form, minutes, find):
        seen["cmd"] = cmd
        yield "ok", "", []
    monkeypatch.setattr(webui, "_stream_clip", fake_stream)
    monkeypatch.setattr(webui, "_pipeline_cmd", lambda: ["py"])
    list(webui.quick_clip("", None, 3, True, reuse=os.path.join(old, "command.json"), reuse_all=True))
    cmd = seen["cmd"]
    assert cmd[cmd.index("--source_video") + 1] == "C:/v/game.mp4" and "--use_cache" in cmd
    session = cmd[cmd.index("--session_dir") + 1]
    assert os.path.isfile(os.path.join(session, "transcript.json")) and os.path.isfile(os.path.join(session, "highlights.json"))
    assert os.path.isfile(os.path.join(session, "temp_segments", "seg_0.mp4"))
    import time
    time.sleep(1.1)                      # session folders are named by the second
    list(webui.quick_clip("", None, 3, True, reuse=os.path.join(old, "command.json"), reuse_all=False))
    cmd = seen["cmd"]
    session = cmd[cmd.index("--session_dir") + 1]
    assert "--use_cache" not in cmd and os.path.isfile(os.path.join(session, "transcript.json")) and not os.path.exists(os.path.join(session, "highlights.json"))
    with pytest.raises(gr.Error):
        list(webui.quick_clip("", None, 3, True))               # nothing to work on


def test_trip_recap_with_an_earlier_recap_reuses_its_videos_and_descriptions(tmp_path, monkeypatch):
    root = str(tmp_path)
    vid = tmp_path / "day1.mp4"
    vid.write_bytes(b"x")
    old = make_run(root, "trip_20261105_090000", ["py", "--mode", "TRIP", "--trip_videos", str(vid)], ["visual_context.json", "places.json"])
    monkeypatch.setattr(webui, "ROOT", root)
    ran = {}

    def fake_run(cmd):
        ran["cmd"] = cmd
        yield "", []
    monkeypatch.setattr(webui, "_run", fake_run)
    monkeypatch.setattr(webui, "_pipeline_cmd", lambda: ["py"])
    list(webui.trip_recap(None, "T", "", "", "", 60, "hype", None, reuse=os.path.join(old, "command.json")))
    cmd = ran["cmd"]
    assert str(vid) in cmd
    session = cmd[cmd.index("--session_dir") + 1]
    assert os.path.isfile(os.path.join(session, "places.json")) and os.path.isfile(os.path.join(session, "command.json"))


def test_reuse_choice_strings_work_like_the_booleans(tmp_path, monkeypatch):
    root = str(tmp_path)
    old = make_run(root, "web_20261104_204742", ["py", "--source_video", "C:/v/game.mp4"], ["transcript.json", "highlights.json"])
    monkeypatch.setattr(webui, "ROOT", root)
    seen = {}

    def fake_stream(cmd, results, long_form, minutes, find):
        seen["cmd"] = cmd
        yield "ok", "", []
    monkeypatch.setattr(webui, "_stream_clip", fake_stream)
    monkeypatch.setattr(webui, "_pipeline_cmd", lambda: ["py"])
    list(webui.quick_clip("", None, 3, True, reuse=os.path.join(old, "command.json"), reuse_all="transcript"))
    assert "--use_cache" not in seen["cmd"]


def test_drive_upload_after_a_clip_run_reports_and_skips_when_empty(monkeypatch, tmp_path):
    from engine import drive_upload
    video = tmp_path / "a.mp4"
    video.write_bytes(b"x")
    sent = []
    monkeypatch.setattr(drive_upload, "upload", lambda paths, folder, **k: sent.append((list(paths), folder)) or [{"name": "a.mp4"}])
    stream = lambda: iter([("done", "log", [{"video": str(video)}])])  # noqa: E731
    out = list(webui._with_drive(stream(), "https://drive.google.com/drive/folders/ABCdef123456"))
    assert out[0][0] == "done" and "Uploading" in out[1][0] and "Uploaded 1 video" in out[-1][0]
    assert sent == [([str(video)], "https://drive.google.com/drive/folders/ABCdef123456")]
    assert len(list(webui._with_drive(stream(), ""))) == 1 and len(sent) == 1          # no folder given: nothing is uploaded
    assert "not a Google Drive folder" in webui.drive_upload_message([str(video)], "nonsense")
