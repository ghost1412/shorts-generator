import subprocess

import imageio_ffmpeg
import numpy as np

from engine import sfx_mix

FF = imageio_ffmpeg.get_ffmpeg_exe()


def test_synth_sounds_have_sane_length_and_peak():
    for kind, seconds in (("whoosh", 0.5), ("pop", 0.14), ("hit", 0.35)):
        s = sfx_mix.synth(kind)
        assert abs(len(s) / sfx_mix.SR - seconds) < 0.01 and 0.5 < np.max(np.abs(s)) <= 0.9 + 1e-6
        assert abs(s[0]) < 0.05 and abs(s[-1]) < 0.05              # faded: no click


def test_clean_events_drops_edges_crowding_and_unknown_kinds():
    ev = [{"t": 0.1, "kind": "pop"}, {"t": 2.0, "kind": "pop"}, {"t": 2.3, "kind": "whoosh"}, {"t": 4.0, "kind": "laser"},
          {"t": 5.0, "kind": "hit"}, {"t": 9.9, "kind": "pop"}]
    out = sfx_mix.clean_events(ev, duration=10.0)
    assert [(e["t"], e["kind"]) for e in out] == [(2.0, "pop"), (5.0, "hit")]


def test_command_has_one_input_per_event_and_copies_the_picture():
    files = {k: f"{k}.wav" for k in sfx_mix.KINDS}
    cmd = sfx_mix.build_command("ff", "in.mp4", [{"t": 1.5, "kind": "pop"}, {"t": 4, "kind": "whoosh"}], files, -16, "out.mp4")
    text = " ".join(cmd)
    assert cmd.count("-i") == 3 and "adelay=1500|1500" in text and "adelay=4000|4000" in text
    assert "amix=inputs=3" in text and "normalize=0" in text and "-c:v copy" in text


def _pcm(path):
    raw = subprocess.run([FF, "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def test_real_mix_adds_sound_only_at_the_event(tmp_path):
    clip = tmp_path / "clip.mp4"
    r = subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=216x384:rate=30:duration=6",
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(clip)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    done = sfx_mix.mix_events(str(clip), [{"t": 3.0, "kind": "whoosh"}], volume_db=-10)
    assert len(done) == 1
    pcm = _pcm(clip)
    rms = lambda a, b: float(np.sqrt(np.mean(pcm[int(a * 16000):int(b * 16000)] ** 2)))        # noqa: E731
    assert rms(3.05, 3.45) > 0.01 and rms(0.2, 2.5) < 0.002 and rms(4.5, 5.8) < 0.002          # sound at 3 s, silence elsewhere
    assert abs(len(pcm) / 16000 - 6.0) < 0.3


def test_failures_leave_the_clip_alone(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"x" * 100)
    assert sfx_mix.mix_events(str(bad), [{"t": 1, "kind": "pop"}]) == [] and bad.read_bytes() == b"x" * 100
