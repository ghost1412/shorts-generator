import os
import shutil
import subprocess

import pytest

from engine import dubbing


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def test_short_path_prefers_the_relative_form(tmp_path):
    deep = tmp_path / "session" / "dub_clips" / "a.mp3"
    assert dubbing._short_path(str(deep), str(tmp_path / "session")) == os.path.join("dub_clips", "a.mp3")


def test_inputs_length_counts_every_clip(tmp_path):
    clips = [{"path": str(tmp_path / f"c{i}.mp3")} for i in range(10)]
    assert dubbing._inputs_length(clips, str(tmp_path)) == sum(len(f"c{i}.mp3") + 4 for i in range(10))


def test_many_dub_clips_are_mixed_in_batches_and_the_video_still_comes_out(tmp_path, monkeypatch):
    try:
        ff = _ffmpeg()
    except Exception:
        pytest.skip("no ffmpeg")
    session = tmp_path / "session"
    (session / "clips").mkdir(parents=True)
    source = session / "src.mp4"
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=160x90:d=4", "-f", "lavfi", "-i", "sine=f=220:d=4",
                        "-shortest", "-c:v", "libx264", "-c:a", "aac", str(source)], capture_output=True)
    if r.returncode != 0:
        pytest.skip("ffmpeg could not make a test video")
    tone = session / "clips" / "tone.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=660:d=0.15", str(tone)], check=True)
    clips = []
    for i in range(25):
        p = session / "clips" / f"dub_segment_with_a_very_long_name_{i:04d}.wav"
        shutil.copy(tone, p)
        clips.append({"path": str(p), "start": i * 0.15, "tempo": 1.0, "trim": None})
    monkeypatch.setattr(dubbing, "CHUNK_CLIPS", 10)
    monkeypatch.setattr(dubbing, "MAX_INPUT_CHARS", 50)           # force the batch path
    out = dubbing.mix_dub(str(source), clips, str(session / "out.mp4"), str(session), original="quiet")
    assert os.path.exists(out)
    assert sorted(f for f in os.listdir(session) if f.startswith("dub_batch_") and f.endswith(".wav")) == ["dub_batch_0.wav", "dub_batch_1.wav", "dub_batch_2.wav"]
    dur = subprocess.run([ff, "-i", out], capture_output=True, text=True).stderr
    assert "Duration: 00:00:04" in dur or "Duration: 00:00:03.9" in dur


def test_unfinished_dubs_are_listed_and_a_finished_one_is_not(tmp_path):
    import json
    from shortsflow import web_args
    sessions = tmp_path / "sessions"
    crashed, done = sessions / "dub_20261110_170226", sessions / "dub_20261109_101500"
    for d in (crashed, done):
        d.mkdir(parents=True)
        (d / "source_video.mp4").write_bytes(b"x")
        (d / "source_video_hi.json").write_text(json.dumps({"target_lang": "hi", "segments": [{"start": 0, "end": 1, "text": "x"}] * 3}), encoding="utf-8")
    (done / "source_video_dub_hi.mp4").write_bytes(b"x")
    listed = web_args.unfinished_dubs(str(tmp_path))
    assert [path for _, path in listed] == [str(crashed)]
    assert "3 lines" in listed[0][0] and "17:02" in listed[0][0]
    assert web_args.read_dub_session(str(crashed))[1:] == ("hi", 3)
    assert web_args.read_dub_session(str(tmp_path)) is None


def test_dub_tab_passes_the_resume_choice_last():
    import ast
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "dub_video")
    assert [a.arg for a in fn.args.args][-3:] == ["resume", "tone", "delivery"]
    assert "d_original, d_resume, d_tone, d_delivery]" in src
