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
    for name in auto_edit.preset_names():
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
