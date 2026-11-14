from engine import auto_edit
from shortsflow import web_args
from shortsflow.ui import kinds


def test_every_kind_uses_real_choices():
    templates = {name for _, name in web_args.VISUAL_TEMPLATE_CHOICES}
    for key, s in kinds.KINDS.items():
        assert s["edit"] in auto_edit.PRESETS, key
        assert s["template"] in templates, key
        assert s["framing"] in ("auto", "fit", "crop"), key
        assert isinstance(s["game"], bool), key


def test_only_gaming_turns_game_mode_on():
    assert [k for k, s in kinds.KINDS.items() if s["game"]] == ["gaming"]
    assert kinds.settings_for("gaming")["framing"] == "crop"


def test_unknown_kind_is_neutral_and_copy_is_safe():
    assert kinds.settings_for("nope") == kinds.KINDS["other"]
    kinds.settings_for("podcast")["edit"] = "changed"
    assert kinds.KINDS["podcast"]["edit"] == "podcast"


def test_choices_and_describe():
    assert ("Gaming", "gaming") in kinds.kind_choices()
    line = kinds.describe("gaming")
    assert "game mode on" in line and "crop" in line and "neon-frame" in line
    assert "moments picked from what is said" in kinds.describe("podcast")


def test_caption_styles_exist_on_the_command_line():
    import os
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "shortsflow", "_main.py"), encoding="utf-8").read()
    line = next(l for l in src.splitlines() if '"--caption_style"' in l)
    allowed = set(re.findall(r'"([A-Z_]+)"', line.split("choices=")[1].split("]")[0]))
    for key, s in kinds.KINDS.items():
        assert s["captions"] in allowed, key


def test_gallery_pick_maps_a_click_to_a_template():
    from shortsflow.ui.blocks import gallery_pick
    names = ["podcast-card", "neon-frame"]
    assert gallery_pick(names, 1) == "neon-frame"
    assert gallery_pick(names, 5) == "none" and gallery_pick(names, None) == "none" and gallery_pick(names, -1) == "none"


def test_picture_choice_reaches_the_command(monkeypatch):
    """The plain 'Picture' choice: fit -> the fit layout, crop -> the game framing (only visible in the source, no gradio needed)."""
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    assert 'picture in ("fit", "crop") and game_framing == "auto"' in src
    assert '(game or picture == "fit")' in src


def test_progress_view_moves_forward_and_shows_detail():
    import re
    from shortsflow import onboarding as o
    p = o.Progress()
    assert p.fraction() == 0.0
    for line in ("--- Starting AI Extraction: x ---", "Transcribe:  45%|###"):
        p.feed(line)
    assert p.detail == "Listening 45%" and 0.2 < p.fraction() < 0.4
    html = p.display()
    assert re.findall(r'<span class="([^"]*)">([^<]*)', html)[:2] == [("done", "Get video"), ("now", "Listen")]
    assert "Getting" not in html or "Listening" in html
    for line in ("Compressing 3 fragments... outline", "Extracting 5 segments", "Rendered 40/80"):
        p.feed(line)
    assert p.detail == "Rendering 50%"
    assert p.fraction() > 0.6
    p.feed("SUCCESS! Extracted videos")
    assert p.fraction() == 1.0 and 'class="now"' not in p.display()


def test_progress_model_download_stage_is_not_drawn_and_dub_has_its_own_stages():
    from shortsflow import onboarding as o
    assert "Model" not in o.Progress().display()
    d = o.Progress(steps=o.DUB_STEPS)
    d.feed("Dubbing 12 spoken segments")
    assert "Dub" in d.display() and "Render" not in d.display()
