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
    assert [v for _, v in web_args.CAPTION_POSITION_CHOICES] == ["default", "top", "middle", "bottom"]


def test_web_quick_clip_inputs_match_its_parameters():
    """The Start-here button passes its inputs by position, so the list must line up with quick_clip's parameters."""
    import inspect
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    m = re.search(r"q_btn\.click\(quick_clip, \[(.*?)\],\s*\[q_status", src, re.S)
    assert m
    inputs = [x.strip() for x in m.group(1).replace("\n", " ").split(",") if x.strip()]
    import webui
    params = list(inspect.signature(webui.quick_clip).parameters)
    assert len(inputs) <= len(params) and inputs[-4:] == ["q_game", "q_game_mix", "q_cap_pos", "q_cap_size"]
    assert params[len(inputs) - 4:len(inputs)] == ["game", "game_mix", "caption_position", "caption_size"]


def test_clip_tab_inputs_match_clip_video_parameters():
    import inspect
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    m = re.search(r"clip_btn\.click\(\s*clip_video,\s*\[(.*?)\],\s*\[clip_log", src, re.S)
    assert m
    inputs = [x.strip() for x in m.group(1).replace("\n", " ").split(",") if x.strip()]
    import webui
    params = list(inspect.signature(webui.clip_video).parameters)
    assert inputs[-4:] == ["clip_game", "clip_game_mix", "clip_cap_pos", "clip_cap_size"]
    # *clip_settings stands for five inputs (style, aspect, remotion, llm, tts)
    assert len(inputs) - 1 + 5 == len(params)
    assert params[-4:] == ["game", "game_mix", "caption_position", "caption_size"]
