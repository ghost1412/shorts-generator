"""The synthesized SFX used to come out twice as long (stereo samples played as mono)."""
import re
import subprocess

import imageio_ffmpeg
import pytest


def _duration(path):
    err = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


@pytest.mark.parametrize("kind,expected", [("whoosh", 1.0), ("rain", 5.0)])
def test_synth_sfx_has_the_requested_length(tmp_path, kind, expected):
    from engine.media_gen import generate_local_sfx
    out = generate_local_sfx(kind, str(tmp_path / f"{kind}.mp3"))
    assert abs(_duration(out) - expected) < 0.15
