"""Regression tests for bugs found by the 2026-11-04 parameter audit."""
import subprocess
import sys

from engine import pipeline
from engine.modes import clip_extract


def test_clip_extract_has_subprocess_at_module_level():
    # `import subprocess` used to live inside `if args.preview:`, so --add_commentary / --show_banner hit UnboundLocalError
    assert clip_extract.subprocess is subprocess


def test_srt_export_lives_in_pipeline():
    # clip_extract imported export_srt from engine.video_gen, which does not have it (ImportError swallowed -> no .srt)
    import engine.video_gen as video_gen
    assert not hasattr(video_gen, "export_srt")
    assert callable(pipeline.export_srt)


def test_srt_export_for_clip_offsets(tmp_path):
    out = tmp_path / "c.srt"
    pipeline.export_srt({"segments": [{"start": 0.0, "end": 1.5, "text": "hello"}]}, str(out))
    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,500" in text and "hello" in text


def test_batch_item_command_video_and_category():
    argv = ["--batch_file", "list.txt", "--use_remotion", "--mode", "DUB", "--category", "ignored"]
    video = pipeline.batch_item_command(argv, "a.mp4", 1, python="py")
    assert video[-2:] == ["--source_video", "a.mp4"] and "--batch_file" not in video and "DUB" in video
    topic = pipeline.batch_item_command(argv, "space mysteries", 2, python="py", as_category=True)
    assert topic[-2:] == ["--category", "space mysteries"]
    assert topic.count("--category") == 1 and "--source_video" not in topic


def test_cli_accepts_setting_flag():
    # --setting was read by the STORY mode but never defined, so every STORY run crashed with AttributeError
    res = subprocess.run([sys.executable, "main.py", "--help"], capture_output=True, text=True, timeout=120)
    assert "--setting" in res.stdout, res.stderr[-500:]


def test_gui_only_sends_values_the_cli_accepts():
    import ast
    import re
    src = open("gui_app.py", encoding="utf-8").read()
    ast.parse(src)
    assert "RANK_IT" not in src            # no such generate mode
    for bad in ("energetic", "calm", "mysterious"):
        assert f'"{bad}"' not in src       # --vibe choices: suspense, spooky, cinematic, upbeat, sarcastic, funny
    assert re.search(r'"--extract_mode", ext_mode', src) and 'ext_mode = "long" if' in src
