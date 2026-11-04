import os

import pytest

from engine import fsutil


def test_replace_file_waits_out_a_momentary_lock(tmp_path, monkeypatch):
    src, dst = tmp_path / "a.tmp", tmp_path / "a.mp4"
    src.write_text("new")
    dst.write_text("old")
    real, calls = os.replace, {"n": 0}

    def flaky(a, b):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(5, "Access is denied")
        return real(a, b)

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(fsutil.time, "sleep", lambda s: None)
    fsutil.replace_file(str(src), str(dst))
    assert dst.read_text() == "new" and calls["n"] == 3


def test_replace_file_gives_up_when_the_file_stays_locked(tmp_path, monkeypatch):
    src = tmp_path / "a.tmp"
    src.write_text("x")
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(5, "Access is denied")))
    monkeypatch.setattr(fsutil.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        fsutil.replace_file(str(src), str(tmp_path / "b.mp4"), tries=3)


def test_every_post_processing_step_swaps_files_through_the_helper():
    for name in ("audio_clean", "sfx_mix", "cold_open", "broll", "branding"):
        src = open(f"engine/{name}.py", encoding="utf-8").read()
        assert "os.replace(" not in src and "replace_file(" in src, name


def test_segments_are_only_trusted_after_ffmpeg_finished(tmp_path):
    from engine.video_gen import finish_segment_processes

    class Proc:
        def __init__(self, code):
            self.returncode = code

        def wait(self):
            return self.returncode

    ok_part, ok_final = tmp_path / "seg_0.part.mp4", tmp_path / "seg_0.mp4"
    bad_part, bad_final = tmp_path / "seg_1.part.mp4", tmp_path / "seg_1.mp4"
    ok_part.write_bytes(b"x" * 5000)
    bad_part.write_bytes(b"x" * 5000)                     # a run that was stopped / crashed leaves a partial file
    finish_segment_processes([(Proc(0), str(ok_part), str(ok_final)), (Proc(1), str(bad_part), str(bad_final))])
    assert ok_final.exists() and not ok_part.exists()
    assert not bad_final.exists() and not bad_part.exists()      # never promoted, and cleaned up
