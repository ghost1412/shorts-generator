import os

from engine import caption_layout as cl


def test_named_positions_and_default():
    assert cl.y_for("default", 1150) == 1150
    assert cl.y_for(None, 1150) == 1150
    assert cl.y_for("top", 1150) < cl.y_for("middle", 1150) < cl.y_for("bottom", 1150)
    assert all(300 <= y <= 1700 for y in cl.POSITIONS.values())      # inside what a re-render accepts


def test_an_explicit_height_beats_a_named_position():
    assert cl.y_for("bottom", 900) == 900


def test_sizes_are_named_or_numeric_and_clamped():
    assert cl.size_for("default") == 1.0 and cl.size_for("small") < 1.0 < cl.size_for("large") < cl.size_for("xlarge")
    assert cl.size_for(5) == 1.8 and cl.size_for(0.1) == 0.6 and cl.size_for("nonsense") == 1.0


def test_renderer_reads_the_size_from_the_environment(monkeypatch):
    from engine.remotion_renderer import _caption_size_from_env
    monkeypatch.delenv("SHORTSFLOW_CAPTION_SIZE", raising=False)
    assert _caption_size_from_env() == 1.0
    monkeypatch.setenv("SHORTSFLOW_CAPTION_SIZE", "1.3")
    assert _caption_size_from_env() == 1.3
    monkeypatch.setenv("SHORTSFLOW_CAPTION_SIZE", "huge")
    assert _caption_size_from_env() == 1.0


def test_cli_has_caption_position_and_size():
    src = open(os.path.join(os.path.dirname(__file__), "..", "shortsflow", "_main.py"), encoding="utf-8").read()
    assert '"--caption_position"' in src and '"--caption_size"' in src


def test_web_form_builds_game_and_caption_options():
    from shortsflow import web_args
    assert web_args.game_args(False) == []
    assert web_args.game_args(True, "0.5") == ["--content", "game", "--game_mix", "0.5"]
    assert web_args.game_args(True, "0") == ["--content", "game", "--game_mix", "0"]
    assert web_args.game_args(True, "oops") == ["--content", "game", "--game_mix", "0.5"]
    assert web_args.caption_look_args("default", "default") == []
    assert web_args.caption_look_args("bottom", "large") == ["--caption_position", "bottom", "--caption_size", "large"]
    assert [v for _, v in web_args.CAPTION_POSITION_CHOICES] == ["default", "top", "middle", "bottom", "off"]


def _webui_source():
    return open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()


def _params(src, name):
    """Parameter names of a top-level function, read from the source (importing webui needs gradio, which CI does not install)."""
    import ast
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return [a.arg for a in node.args.args]
    raise AssertionError(name + " not found")


def _click_inputs(src, pattern):
    import re
    m = re.search(pattern, src, re.S)
    assert m
    return [x.strip() for x in m.group(1).replace("\n", " ").split(",") if x.strip()]


def test_web_quick_clip_inputs_match_its_parameters():
    """The Start-here button passes its inputs by position, so the list must line up with quick_clip's parameters."""
    src = _webui_source()
    inputs = _click_inputs(src, r"q_btn\.click\(quick_clip, \[(.*?)\],\s*\[q_status")
    params = _params(src, "quick_clip")
    # the last group, *q_look, stands for the ten look inputs (visual template, covers, template text, frame shape)
    assert inputs[-9:] == ["q_game", "q_game_mix", "q_cap_pos", "q_cap_size", "q_game_frame", "q_llm", "*q_look", "q_plan_first", "q_between"]
    assert len(inputs) - 1 + 10 == len(params)
    assert params[-18:-2] == ["game", "game_mix", "caption_position", "caption_size", "game_framing", "llm_provider", 'visual_template', 'intro_animation', 'outro_animation', 'tpl_speaker', 'tpl_role', 'tpl_show', 'tpl_handle', 'tpl_headline', 'tpl_cta', 'shape']
    assert params[-2:] == ["plan_first", "between"]


def test_clip_tab_inputs_match_clip_video_parameters():
    src = _webui_source()
    inputs = _click_inputs(src, r"clip_btn\.click\(\s*clip_video,\s*\[(.*?)\],\s*\[clip_log")
    params = _params(src, "clip_video")
    assert inputs[-6:] == ["clip_game", "clip_game_mix", "clip_cap_pos", "clip_cap_size", "clip_game_frame", "*clip_look"]
    assert len(inputs) - 2 + 5 + 9 == len(params)       # *clip_settings stands for five inputs (style, aspect, remotion, llm, tts), *clip_look for nine
    assert params[-14:] == ["game", "game_mix", "caption_position", "caption_size", "game_framing", 'visual_template', 'intro_animation', 'outro_animation', 'tpl_speaker', 'tpl_role', 'tpl_show', 'tpl_handle', 'tpl_headline', 'tpl_cta']
