import json
import shutil
import subprocess

import pytest

from engine import visual_context as vc
from engine.highlight_rank import build_prompt


def test_pick_vision_model_prefers_known_families(monkeypatch):
    monkeypatch.delenv("SHORTSFLOW_VISION_MODEL", raising=False)
    assert vc.pick_vision_model(["qwen2.5:7b", "llava:13b", "gemma3:12b"]) == "gemma3:12b"
    assert vc.pick_vision_model(["qwen2.5:7b", "llama3.2:3b"]) is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_VISION_MODEL", "my-vlm")
    assert vc.pick_vision_model([]) == "my-vlm"


def test_clean_description_strips_lead_in():
    assert vc.clean_description("Here's a description of what is happening:\n\nKratos fights Zeus.\n") == "Kratos fights Zeus."
    assert vc.clean_description(None) == ""


def test_describe_candidates_caches_and_skips_failures(tmp_path):
    cache = tmp_path / "vc.json"
    calls = []

    def ask(frames, model, about):
        calls.append(model)
        return "A cutscene" if frames else ""

    hl = [{"start": 10, "end": 40}, {"start": 50, "end": 80}]
    grab = lambda v, s, e: [b"x"] if s < 20 else []
    out = vc.describe_candidates("v.mp4", hl, cache_path=str(cache), model="m", grab=grab, ask=ask)
    assert out[0]["visual"] == "A cutscene" and "visual" not in out[1]
    assert "visual" not in hl[0]                       # input untouched
    assert json.loads(cache.read_text())["10.0-40.0"] == "A cutscene"
    calls.clear()
    vc.describe_candidates("v.mp4", hl, cache_path=str(cache), model="m", grab=grab, ask=ask)
    assert len(calls) == 1                             # only the one without a cached answer is asked again


def test_no_model_leaves_highlights(monkeypatch, capsys):
    monkeypatch.delenv("SHORTSFLOW_VISION_MODEL", raising=False)
    monkeypatch.setattr(vc, "installed_models", lambda *a, **k: [])
    hl = [{"start": 1, "end": 20}]
    assert vc.describe_candidates("v.mp4", hl) == hl
    assert "ollama pull" in capsys.readouterr().out


def test_ranking_prompt_includes_context_and_screen():
    spans = [(0.0, 5.0, "Hello everyone."), (5.0, 12.0, "Look at this.")]
    h = [{"start": 0.0, "end": 12.0, "visual": "Kratos faces Zeus in a cutscene"}]
    p = build_prompt(h, spans, 12.0, context="God of War 3 playthrough")
    assert "About this video: God of War 3 playthrough" in p
    assert "ON SCREEN: Kratos faces Zeus" in p
    plain = build_prompt([{"start": 0.0, "end": 12.0}], spans, 12.0)
    assert "ON SCREEN" not in plain and "About this video" not in plain


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")
def test_grab_frames_real_ffmpeg(tmp_path):
    video = tmp_path / "t.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=6",
                    str(video)], check=True)
    frames = vc.grab_frames(str(video), 0, 6, ffmpeg="ffmpeg")
    assert len(frames) == 3 and frames[0][:2] == b"\xff\xd8"
