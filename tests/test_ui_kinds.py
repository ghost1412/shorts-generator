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
    assert 'layout = web_picture_layout(filler, game, game_framing, picture, long_form)' in src


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


def test_picture_layout_for_start_here_runs():
    """Regression: ticking game footage used to force `--layout fit`, so 'Fill the screen (crop)' was ignored."""
    import os
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "webui.py"), encoding="utf-8").read()
    body = re.search(r"def web_picture_layout\(.*?\n\n\n", src, re.S).group(0)
    ns = {}
    exec(body, ns)
    f = ns["web_picture_layout"]
    assert f(False, True, "crop", "crop", False) == "single"       # game + crop: no fit layout
    assert f(False, True, "auto", "auto", False) == "single"       # game + automatic: the tool decides
    assert f(False, True, "fit", "fit", False) == "fit"
    assert f(False, False, "auto", "fit", False) == "fit"
    assert f(False, False, "auto", "crop", False) == "auto"
    assert f(True, True, "crop", "crop", False) == "split_filler"
    assert f(False, True, "crop", "crop", True) == "auto"          # highlights video


def test_trip_wording_for_the_template_text_boxes():
    from shortsflow import web_args
    from shortsflow.ui import blocks
    assert len(blocks.TRIP_TEXT_LABELS) == len(blocks.DEFAULT_TEXT_LABELS) == len(web_args.TEMPLATE_TEXT_SLOTS)
    slot = web_args.TEMPLATE_TEXT_SLOTS.index("show")
    assert blocks.TRIP_TEXT_LABELS[slot][0] == "Trip name"          # the box that feeds the main title says what it is
    assert "channel" not in " ".join(label for label, _ in blocks.TRIP_TEXT_LABELS).lower()
    assert blocks.DEFAULT_TEXT_LABELS[slot][0] == "Show or channel"  # clips keep their wording


def test_template_trip_name_falls_back_to_the_recaps_trip_name():
    from shortsflow import web_args
    assert web_args.recap_template_show("", "  Northvale  trip ") == "Northvale trip"
    assert web_args.recap_template_show("My own", "Northvale") == "My own"
    assert web_args.recap_template_show(None, None) == ""


def test_pasted_local_paths_are_used_in_place(tmp_path):
    from shortsflow import web_args
    day1 = tmp_path / "day1"
    day1.mkdir()
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"x")
    text = f'  "{day1}"  \n\n{clip}\n{tmp_path / "missing"}\n{day1}\n'
    assert web_args.local_paths(text) == [str(day1), str(clip)]        # quotes and blanks ignored, missing skipped, no duplicates
    assert web_args.local_paths("") == [] and web_args.local_paths(None) == []
