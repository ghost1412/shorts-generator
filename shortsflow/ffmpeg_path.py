"""Make `ffmpeg` resolvable by name.

Whisper (stable-ts) and several pipeline steps start `ffmpeg` / `ffprobe` by name, which fails on a PC that has no FFmpeg on
its PATH. The pip package already ships an FFmpeg binary through `imageio-ffmpeg`, but under a long file name
(ffmpeg-win-x86_64-v7.1.exe). When nothing named `ffmpeg` is on the PATH, copy that binary to <workspace>/.bin/ffmpeg(.exe)
and put the folder first on PATH. (`ffprobe` is not bundled; the Windows installer downloads a full FFmpeg that has it.)
"""
import os
import shutil
import sys


def ensure_ffmpeg_on_path(home):
    """True when `ffmpeg` can be found by name afterwards."""
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg
        source = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return False
    if not source or not os.path.exists(source):
        return False
    try:
        bin_dir = os.path.join(home, ".bin")
        os.makedirs(bin_dir, exist_ok=True)
        target = os.path.join(bin_dir, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if not os.path.exists(target) or os.path.getsize(target) != os.path.getsize(source):
            shutil.copy2(source, target)
            os.chmod(target, 0o755)
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    except OSError:
        return False
    return bool(shutil.which("ffmpeg"))
