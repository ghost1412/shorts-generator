import argparse
import json

import pytest

from engine import auto_edit


def _args(**kw):
    base = dict(tighten=False, remove_fillers=False, clean_audio=False, hook_overlay=False, auto_zoom=False, cold_open=False, broll=False,
                caption_emoji=False, use_remotion=False, tighten_mode="speed", caption_style="HORMOZI", video_filter="none")
    base.update(kw)
    return argparse.Namespace(**base)


def test_every_preset_turns_on_the_basics_and_exports_the_zoom_strength(monkeypatch):
    for name in auto_edit.BUILTIN_NAMES[:4]:          # podcast, hype, educational, vlog: the original four always cut, hook and zoom
        a = _args()
        plan = auto_edit.apply_preset(a, name, "medium", [])
        assert a.tighten and a.remove_fillers is (name != "vlog") and a.clean_audio and a.use_remotion and a.hook_overlay and a.auto_zoom
        assert a.tighten_mode == "cut" and plan["preset"] == name and plan["flags"]["caption_style"] == a.caption_style
        assert a.auto_edit_cfg["sfx_db"] < 0
    import os
    assert os.environ["SHORTSFLOW_ZOOM_INTENSITY"] == "1.0" and os.environ["SHORTSFLOW_ZOOM_SPACING"] == "3.5"


def test_the_users_own_choices_win():
    a = _args(caption_style="MINIMAL", video_filter="moody_dark", cold_open=True)
    auto_edit.apply_preset(a, "hype", "medium", ["--caption_style", "MINIMAL", "--video_filter=moody_dark"])
    assert a.caption_style == "MINIMAL" and a.video_filter == "moody_dark" and a.cold_open is True      # not overridden, not switched off
    b = _args()
    auto_edit.apply_preset(b, "hype", "medium", [])
    assert b.caption_style == "KARAOKE" and b.video_filter == "vibrant_action" and b.caption_emoji


def test_strength_changes_how_much_shows():
    subtle, hyped = _args(), _args()
    auto_edit.apply_preset(subtle, "hype", "subtle", [])
    auto_edit.apply_preset(hyped, "podcast", "hyped", [])
    assert not subtle.cold_open and not subtle.broll and not subtle.caption_emoji           # subtle: quiet edit
    assert hyped.cold_open and hyped.caption_emoji                                          # hyped: full toolbox, even for a podcast
    assert subtle.auto_edit_cfg["zoom_intensity"] < hyped.auto_edit_cfg["zoom_intensity"]
    assert subtle.auto_edit_cfg["sfx_db"] < hyped.auto_edit_cfg["sfx_db"]
    edu = _args()
    auto_edit.apply_preset(edu, "educational", "medium", [])
    assert not edu.cold_open and edu.broll                                                  # explainers get cutaways, no teaser


def test_unknown_choices_are_plain_errors():
    with pytest.raises(ValueError, match="auto-edit style"):
        auto_edit.apply_preset(_args(), "nope")
    with pytest.raises(ValueError, match="strength"):
        auto_edit.apply_preset(_args(), "hype", "loud")


def test_sfx_events_follow_the_edits_and_shift_with_a_cold_open():
    cfg = {"sfx": {"zoom": "pop", "broll": "whoosh", "cut": "hit"}}
    zooms = [{"start": 4.0, "end": 5.0}, {"start": 9.0, "end": 10.0}]
    broll = [{"t": 6.0, "keyword": "money"}]
    plain = auto_edit.build_sfx_events(cfg, zooms, broll, None)
    assert [(e["t"], e["kind"]) for e in plain] == [(4.0, "pop"), (6.0, "whoosh"), (9.0, "pop")]
    shifted = auto_edit.build_sfx_events(cfg, zooms, broll, {"duration": 3.0})
    assert [(e["t"], e["kind"]) for e in shifted] == [(3.0, "hit"), (7.0, "pop"), (9.0, "whoosh"), (12.0, "pop")]
    assert "money" in shifted[2]["why"]
    assert auto_edit.build_sfx_events({"sfx": {"zoom": None, "broll": None, "cut": None}}, zooms, broll, {"duration": 3.0}) == []
    assert auto_edit.build_sfx_events(None, zooms, broll, None) == []


def test_rhythm_finds_the_flat_stretches():
    r = auto_edit.rhythm([{"start": 3.0}], [], None, 20.0)
    assert r["longest_static"] == 17.0 and r["static_stretches"] == [[3.0, 20.0]]
    r2 = auto_edit.rhythm([{"start": 4.0}, {"start": 8.0}, {"start": 12.0}, {"start": 16.0}], [], None, 20.0)
    assert r2["longest_static"] == 4.0 and r2["static_stretches"] == []


def test_summary_is_plain_language():
    line = auto_edit.summarize({"tightened": True, "zooms": 4, "broll": 1, "cold_open": 4.7, "sfx": 6, "grade": "cinematic_warm",
                                "captions": "KARAOKE", "rhythm": {"static_stretches": [[8.0, 15.0]]}})
    assert "4 zooms" in line and "1 cutaway" in line and "4.7 s teaser" in line and "6 sound effects" in line
    assert "cinematic warm colour" in line and "karaoke captions" in line and "calm stretch 8-15 s" in line
    assert auto_edit.summarize({}) == ""


def test_settings_roundtrip_and_plan_file(tmp_path):
    cfg = auto_edit.cfg_from_settings({"auto_edit": "vlog", "edit_strength": "hyped"})
    assert cfg["preset"] == "vlog" and cfg["sfx_db"] == -13.0 and auto_edit.cfg_from_settings({"auto_edit": None}) is None
    path = auto_edit.write_plan(str(tmp_path), {"preset": "vlog"}, [{"clip": "a.mp4"}])
    assert json.load(open(path))["clips"][0]["clip"] == "a.mp4"
    assert auto_edit.read_zoom_moments(str(tmp_path / "none.mp4")) == []


def test_slow_pushes_get_no_sound_only_quick_punch_ins_do():
    cfg = {"sfx": {"zoom": "pop", "broll": None, "cut": None}}
    zooms = [{"start": 3.0, "end": 4.1}, {"start": 10.0, "end": 12.6}]               # a punch (1.1 s) and a slow push (2.6 s)
    assert [(e["t"], e["kind"]) for e in auto_edit.build_sfx_events(cfg, zooms, [], None)] == [(3.0, "pop")]


def test_new_builtin_templates_all_work_and_use_known_values():
    from engine import video_gen
    assert len(auto_edit.BUILTIN_NAMES) >= 10
    for name in auto_edit.BUILTIN_NAMES:
        a = _args()
        auto_edit.apply_preset(a, name, "medium", [])
        p = auto_edit.PRESETS[name]
        assert p["label"] and p["about"] and p["caption_style"] in auto_edit.CAPTION_STYLES
        assert p["video_filter"] is None or p["video_filter"] in video_gen.FILTER_PRESETS
        assert all(v is None or v in auto_edit.SFX_KINDS for v in p["sfx"].values())
    assert set(auto_edit.GRADES) <= set(video_gen.FILTER_PRESETS)


def test_the_tutorial_template_sets_the_layout_unless_the_user_chose_one():
    a = _args(layout="single")
    auto_edit.apply_preset(a, "tutorial", "medium", [])
    assert a.layout == "fit"
    b = _args(layout="split")
    auto_edit.apply_preset(b, "tutorial", "medium", ["--layout", "split"])
    assert b.layout == "split"


def test_user_templates_load_inherit_and_bad_files_are_reported(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    (d / "my-look.json").write_text(json.dumps({"based_on": "podcast", "caption_style": "NEON", "sfx": {"zoom": "pop"}, "layout": "fit"}), encoding="utf-8")
    (d / "child.json").write_text(json.dumps({"based_on": "my-look", "label": "Child", "caption_emoji": True}), encoding="utf-8")
    (d / "_example.json").write_text("{}", encoding="utf-8")
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    (d / "bad-style.json").write_text(json.dumps({"caption_style": "COMIC"}), encoding="utf-8")
    (d / "bad-key.json").write_text(json.dumps({"colour": "red"}), encoding="utf-8")
    (d / "bad-parent.json").write_text(json.dumps({"based_on": "nope"}), encoding="utf-8")
    (d / "Bad Name.json").write_text("{}", encoding="utf-8")
    found, problems = auto_edit.load_templates([str(d)])
    assert sorted(found) == ["child", "my-look"]
    assert found["my-look"]["caption_style"] == "NEON" and found["my-look"]["tighten"] and found["my-look"]["sfx"]["zoom"] == "pop"
    assert found["my-look"]["sfx"]["broll"] == "whoosh"                       # inherited from podcast
    assert found["child"]["caption_style"] == "NEON" and found["child"]["caption_emoji"] is True and found["child"]["label"] == "Child"
    assert found["my-look"]["label"] == "My Look"
    assert len(problems) == 5 and not any("_example" in p for p in problems)
    assert "auto_edit.PRESETS" and "my-look" not in auto_edit.PRESETS         # loading alone does not register


def test_a_template_without_based_on_starts_neutral_and_the_shipped_example_is_valid(tmp_path):
    d = tmp_path / "t"
    d.mkdir()
    (d / "plain.json").write_text(json.dumps({"caption_style": "BAR"}), encoding="utf-8")
    found, problems = auto_edit.load_templates([str(d)])
    assert not problems and found["plain"]["auto_zoom"] is False and found["plain"]["tighten"] is True
    a = _args()
    saved = dict(auto_edit.PRESETS)
    try:
        auto_edit.PRESETS.update(found)
        auto_edit.apply_preset(a, "plain", "medium", [])
        assert a.caption_style == "BAR" and a.use_remotion
    finally:
        auto_edit.PRESETS.clear()
        auto_edit.PRESETS.update(saved)
    import shutil, os
    ex = tmp_path / "ex"
    ex.mkdir()
    shutil.copy(os.path.join(os.path.dirname(auto_edit.__file__), "..", "templates", "_example.json"), ex / "example-copy.json")
    f2, p2 = auto_edit.load_templates([str(ex)])
    assert not p2 and f2["example-copy"]["caption_style"] == "GLOW_BOX"


def test_a_template_saved_from_the_browser_settings_round_trips(tmp_path, monkeypatch):
    from shortsflow import web_args
    saved = dict(auto_edit.PRESETS)
    try:
        ok, msg = web_args.save_look_template("My Channel", "podcast", "MARKER", clean_audio=True, hook_overlay=True, caption_emoji=True, grade="teal_orange",
                                              visual="neon-frame", intro="tiles", outro="iris", folder=str(tmp_path))
        assert ok and "my-channel" in msg and "--auto_edit my-channel" in msg
        data = json.loads((tmp_path / "my-channel.json").read_text(encoding="utf-8"))
        assert data["caption_style"] == "MARKER" and data["caption_emoji"] is True and data["video_filter"] == "teal_orange"
        assert data["visual"] == "neon-frame" and data["intro_animation"] == "tiles" and data["outro_animation"] == "iris"
        assert data["sfx"]["broll"] == "whoosh" and data["label"] == "My Channel"                 # the podcast style's sound effects came along
        found, problems = auto_edit.load_templates([str(tmp_path)])                              # and the file loads again without problems
        assert not problems and found["my-channel"]["caption_style"] == "MARKER"
        assert "my-channel" in auto_edit.PRESETS and ("My Channel", "my-channel") in auto_edit.preset_choices()
        a = _args(visual_template=None, intro_animation=None, outro_animation=None)
        plan = auto_edit.apply_preset(a, "my-channel", "medium", [])
        assert a.visual_template == "neon-frame" and a.intro_animation == "tiles" and plan["flags"]["visual_template"] == "neon-frame"
        # saving again under the same name replaces the user's file; built-in names and bad names are refused with a plain message
        assert web_args.save_look_template("my channel", "none", "SOFT", folder=str(tmp_path))[0]
        assert json.loads((tmp_path / "my-channel.json").read_text(encoding="utf-8"))["caption_style"] == "SOFT"
        for bad, word in (("podcast", "built-in"), ("", "name"), ("a/b", "name"), ("x" * 40, "name")):
            ok, msg = web_args.save_look_template(bad, folder=str(tmp_path))
            assert not ok and word in msg and msg.startswith("Not saved")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["my-channel.json"]                 # nothing else was written
    finally:
        auto_edit.PRESETS.clear()
        auto_edit.PRESETS.update(saved)


def test_edit_style_choices_follow_the_current_templates():
    from shortsflow import web_args
    assert web_args.edit_style_choices()[0] == ("No auto-edit (pick my own options)", "none")
    assert [v for _, v in web_args.edit_style_choices()[1:]] == list(auto_edit.PRESETS)
