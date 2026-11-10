"""Small FFmpeg differences between versions.

Newer FFmpeg builds (8.x) no longer know `-filter_complex_script <file>`; they read a filter graph from a file with
`-/filter_complex <file>` instead, which older builds (before 7.0) do not know. A long filter graph must go in a file because a
command line is limited (about 32,000 characters on Windows), so every caller asks here which spelling this FFmpeg takes.
"""
import functools
import os
import subprocess
import tempfile


@functools.lru_cache(maxsize=8)
def _old_flag_works(ffmpeg):
    """True when this FFmpeg accepts `-filter_complex_script` (tested once per binary on a tiny silent graph)."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "g.txt")
            with open(script, "w", encoding="utf-8") as f:
                f.write("[0:a]anull[a]")
            r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=d=0.05",
                                "-filter_complex_script", script, "-map", "[a]", "-f", "null", "-"],
                               capture_output=True, text=True, timeout=30)
            return r.returncode == 0
    except Exception:
        return True                                  # cannot tell: keep the spelling every older build understands


def filter_complex_script_args(ffmpeg, script_path):
    """The two arguments that load a filter graph from `script_path`, spelled the way this FFmpeg understands."""
    if _old_flag_works(ffmpeg):
        return ["-filter_complex_script", script_path]
    return ["-/filter_complex", script_path]
