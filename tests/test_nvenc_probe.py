import types

import engine.video_gen as vg


def _run_factory(listed, encode_rc):
    def run(cmd, **kw):
        if "-encoders" in cmd:
            return types.SimpleNamespace(stdout=" V....D h264_nvenc NVIDIA NVENC" if listed else " V....D libx264", returncode=0)
        return types.SimpleNamespace(stdout=b"", returncode=encode_rc)
    return run


def test_nvenc_needs_a_real_test_encode_not_just_a_listing(monkeypatch):
    monkeypatch.setattr(vg.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "ffmpeg")
    for listed, rc, expected in ((True, 0, True), (True, 1, False), (False, 0, False)):
        monkeypatch.setattr(vg, "_nvenc_probe", None)
        monkeypatch.setattr(vg.subprocess, "run", _run_factory(listed, rc))
        assert vg._check_nvenc() is expected, (listed, rc)


def test_probe_result_is_cached(monkeypatch):
    monkeypatch.setattr(vg, "_nvenc_probe", True)
    monkeypatch.setattr(vg.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    assert vg._check_nvenc() is True
