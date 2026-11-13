import argparse
import json
import os
import re

import pytest

from engine import auto_edit, visual_template


def test_text_slots_parse_trim_and_reject_unknown():
    assert visual_template.parse_text(["speaker=  Alex   Morgan ", "role=Host", "cta="]) == {"speaker": "Alex Morgan", "role": "Host"}
    assert len(visual_template.parse_text(["headline=" + "x" * 500])["headline"]) == visual_template.MAX_TEXT
    for bad in ("speaker", "colour=red", "=x"):
        with pytest.raises(ValueError, match="KEY=VALUE"):
            visual_template.parse_text([bad])
    assert visual_template.parse_text(None) == {}


def test_env_roundtrip_gives_the_renderer_props():
    env = {}
    visual_template.set_env("podcast-card", {"speaker": "Alex"}, "#ffb703", env)
    assert visual_template.props_from_env(env) == {"visualTemplate": "podcast-card", "templateText": {"speaker": "Alex"}, "templateAccent": "#FFB703"}
    visual_template.set_env("neon-frame", {}, "not a colour", env)
    assert visual_template.props_from_env(env) == {"visualTemplate": "neon-frame"}
    visual_template.set_env("", environ=env)
    assert visual_template.props_from_env(env) == {} and not env
    with pytest.raises(ValueError, match="Unknown visual template"):
        visual_template.set_env("nope", environ={})
    assert visual_template.props_from_env({visual_template.ENV_NAME: "nope"}) == {}
    assert visual_template.props_from_env({visual_template.ENV_NAME: "minimal-line", visual_template.ENV_TEXT: "{broken"}) == {"visualTemplate": "minimal-line"}


def test_overlay_props_carries_the_template(monkeypatch):
    from engine.remotion_renderer import overlay_props
    monkeypatch.setenv(visual_template.ENV_NAME, "news-banner")
    monkeypatch.setenv(visual_template.ENV_TEXT, json.dumps({"headline": "Big news"}))
    props = overlay_props()
    assert props["visualTemplate"] == "news-banner" and props["templateText"] == {"headline": "Big news"}
    monkeypatch.delenv(visual_template.ENV_NAME)
    assert "visualTemplate" not in overlay_props()


def test_python_and_remotion_agree_on_the_template_names():
    root = os.path.join(os.path.dirname(auto_edit.__file__), "..", "remotion-video", "src")
    tsx = open(os.path.join(root, "visualTemplates.tsx"), encoding="utf-8").read()
    listed = re.search(r"VISUAL_TEMPLATES = \[(.*?)\] as const", tsx, re.S).group(1)
    assert tuple(re.findall(r'"([a-z-]+)"', listed)) == auto_edit.VISUAL_TEMPLATE_NAMES
    for name in auto_edit.VISUAL_TEMPLATE_NAMES:
        assert f'case "{name}"' in tsx and auto_edit.VISUAL_TEMPLATES[name]["about"]
        assert os.path.exists(os.path.join(os.path.dirname(auto_edit.__file__), "..", "docs", "templates", name + ".jpg")), name


def test_a_clip_template_can_choose_a_visual_template(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    (d / "show.json").write_text(json.dumps({"based_on": "podcast", "visual": "podcast-card"}), encoding="utf-8")
    (d / "bad.json").write_text(json.dumps({"visual": "sparkles"}), encoding="utf-8")
    found, problems = auto_edit.load_templates([str(d)])
    assert found["show"]["visual"] == "podcast-card" and len(problems) == 1 and "visual must be" in problems[0]
    base = dict(tighten=False, remove_fillers=False, clean_audio=False, hook_overlay=False, auto_zoom=False, cold_open=False, broll=False,
                caption_emoji=False, use_remotion=False, tighten_mode="cut", caption_style="HORMOZI", video_filter="none", visual_template=None)
    saved = dict(auto_edit.PRESETS)
    try:
        auto_edit.PRESETS.update(found)
        a = argparse.Namespace(**base)
        assert auto_edit.apply_preset(a, "show", "medium", [])["flags"]["visual_template"] == "podcast-card" and a.visual_template == "podcast-card"
        b = argparse.Namespace(**dict(base, visual_template="neon-frame"))
        auto_edit.apply_preset(b, "show", "medium", ["--visual_template", "neon-frame"])
        assert b.visual_template == "neon-frame"             # the user's choice wins
    finally:
        auto_edit.PRESETS.clear()
        auto_edit.PRESETS.update(saved)
