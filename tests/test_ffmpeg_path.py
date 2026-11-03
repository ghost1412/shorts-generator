import os
import sys
import types

from shortsflow import ffmpeg_path as fp


def test_nothing_to_do_when_ffmpeg_is_already_on_the_path(monkeypatch, tmp_path):
    monkeypatch.setattr(fp.shutil, "which", lambda name: "C:/tools/ffmpeg.exe")
    assert fp.ensure_ffmpeg_on_path(str(tmp_path)) is True
    assert not (tmp_path / ".bin").exists()


def test_bundled_binary_is_exposed_as_plain_ffmpeg(monkeypatch, tmp_path):
    exe = tmp_path / "ffmpeg-win-x86_64-v7.1.exe"
    exe.write_bytes(b"fake binary")
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", types.SimpleNamespace(get_ffmpeg_exe=lambda: str(exe)))
    seen = {"bin": None}

    def which(name):
        return seen["bin"] and os.path.join(seen["bin"], "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg") \
            if os.path.exists(os.path.join(str(tmp_path / "home" / ".bin"), "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")) else None

    monkeypatch.setattr(fp.shutil, "which", lambda name: which(name))
    seen["bin"] = str(tmp_path / "home" / ".bin")
    monkeypatch.setenv("PATH", "X")
    assert fp.ensure_ffmpeg_on_path(str(tmp_path / "home")) is True
    shim = tmp_path / "home" / ".bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    assert shim.read_bytes() == b"fake binary"
    assert os.environ["PATH"].startswith(str(tmp_path / "home" / ".bin"))


def test_returns_false_without_any_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(fp.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)   # import fails
    assert fp.ensure_ffmpeg_on_path(str(tmp_path)) is False
