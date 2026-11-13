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
    assert [a.arg for a in fn.args.args][-6:] == ["resume", "tone", "delivery", "llm_provider", "caption_size", "caption_position"]
    assert "d_original, d_resume, d_tone, d_delivery, d_llm, d_cap_size, d_cap_pos]" in src


def test_ai_provider_flag_only_when_a_provider_is_picked():
    from shortsflow import web_args
    assert web_args.llm_args("auto") == [] and web_args.llm_args("") == [] and web_args.llm_args(None) == []
    assert web_args.llm_args("ollama") == ["--llm_provider", "ollama"]
    assert web_args.dub_args("v.mp4", "es") == web_args.dub_args("v.mp4", "es", llm_provider="auto")
    assert web_args.trip_args(["a.mp4"], "s") == web_args.trip_args(["a.mp4"], "s", llm_provider="auto")
    dub = web_args.dub_args("v.mp4", "es", llm_provider="ollama")
    trip = web_args.trip_args(["a.mp4"], "s", llm_provider="groq")
    assert dub[dub.index("--llm_provider") + 1] == "ollama" and trip[trip.index("--llm_provider") + 1] == "groq"
    assert [v for _, v in web_args.AI_PROVIDER_CHOICES][0] == "auto"


def test_recap_and_start_here_inputs_end_with_the_provider():
    import ast
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    fns = {n.name: [a.arg for a in n.args.args] for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    assert fns["trip_recap"][-1] == "steps" and fns["trip_recap"][-2] == "llm_provider" and fns["quick_clip"][-11] == "llm_provider" and fns["quick_clip"][-1] == "shape"
    assert "t_lines, t_open_result, t_llm, t_steps]" in src


def test_filter_script_flag_follows_what_this_ffmpeg_understands(monkeypatch):
    from engine import ffmpeg_compat as fc
    fc._old_flag_works.cache_clear()
    monkeypatch.setattr(fc, "_old_flag_works", lambda exe: True)
    assert fc.filter_complex_script_args("ff", "g.txt") == ["-filter_complex_script", "g.txt"]
    monkeypatch.setattr(fc, "_old_flag_works", lambda exe: False)
    assert fc.filter_complex_script_args("ff", "g.txt") == ["-/filter_complex", "g.txt"]


def test_the_chosen_spelling_really_runs_on_this_ffmpeg(tmp_path):
    """The check that failed in CI: a newer FFmpeg refuses -filter_complex_script. Whatever this FFmpeg is, the helper's flag must work."""
    from engine import ffmpeg_compat as fc
    try:
        ff = _ffmpeg()
    except Exception:
        pytest.skip("no ffmpeg")
    fc._old_flag_works.cache_clear()
    script = tmp_path / "g.txt"
    script.write_text("[0:a]anull[a]", encoding="utf-8")
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=d=0.05",
           *fc.filter_complex_script_args(ff, str(script)), "-map", "[a]", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
