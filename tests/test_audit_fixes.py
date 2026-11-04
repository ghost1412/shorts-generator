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


def test_failed_clip_does_not_shift_the_other_clips_onto_the_wrong_highlight():
    hl = [{"start": 0}, {"start": 10}, {"start": 20}, {"start": 30}]
    # clip 2 failed to render; the worker threads finished in the order 4, 1, 3
    files = ["s/video_clip_4.mp4", "s/video_clip_1.mp4", "s/video_clip_3.mp4"]
    h, f = clip_extract.align_clips_with_highlights(hl, files)
    assert f == ["s/video_clip_1.mp4", "s/video_clip_3.mp4", "s/video_clip_4.mp4"]
    assert [x["start"] for x in h] == [0, 20, 30]


def test_alignment_leaves_reels_and_odd_names_alone():
    hl = [{"start": 0}, {"start": 10}]
    assert clip_extract.align_clips_with_highlights(hl, ["s/highlights_reel.mp4"], "long") == (hl, ["s/highlights_reel.mp4"])
    assert clip_extract.align_clips_with_highlights(hl, ["s/mashup_reel.mp4"], "shorts", True) == (hl, ["s/mashup_reel.mp4"])
    assert clip_extract.align_clips_with_highlights(hl, ["s/other.mp4"]) == (hl, ["s/other.mp4"])
    assert clip_extract.align_clips_with_highlights(hl, [])[1] == []


def test_remotion_quality_flags():
    from engine.remotion_renderer import quality_flags
    assert quality_flags({}) == ["--crf=16"]                                         # default output unchanged
    assert quality_flags({"SHORTSFLOW_QUALITY": "high"}) == ["--crf=12"]
    assert quality_flags({"SHORTSFLOW_QUALITY": "ultra", "SHORTSFLOW_BITRATE": "9000k"}) == ["--video-bitrate=9000k"]
    assert quality_flags({"SHORTSFLOW_QUALITY": "nonsense"}) == ["--crf=16"]


def test_markers_stop_brand_and_audio_clean_being_applied_twice(tmp_path):
    clip = str(tmp_path / "video_clip_1.mp4")
    open(clip, "wb").write(b"x")
    kit = {"logo": "a.png", "handle": "@me"}
    assert not clip_extract.already_done(clip, "branded", kit)
    clip_extract.mark_done(clip, "branded", kit)
    assert clip_extract.already_done(clip, "branded", kit)
    assert not clip_extract.already_done(clip, "branded", {"logo": "b.png", "handle": "@me"})   # changed kit: apply again
    assert not clip_extract.already_done(clip, "clean", True)
