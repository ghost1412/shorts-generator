from engine import game_framing as gf
from shortsflow import web_args


def s(hud=0.0, sub=0.0):
    return {"hud": hud, "subtitle": sub}


def test_a_hud_or_subtitles_at_the_sides_keep_the_whole_picture():
    assert gf.decide([s(0.03), s(0.03), s(0.0)])[0] == "fit"
    assert gf.decide([s(0.0, 0.01), s(0.0), s(0.0)])[0] == "fit"       # one of three moments is enough: fit is the safe choice


def test_a_clean_picture_gets_the_crop():
    assert gf.decide([s(0.001), s(0.0), s(0.002), s(0.0)])[0] == "crop"


def test_nothing_measurable_falls_back_to_fit():
    assert gf.decide([None, None])[0] == "fit"
    assert gf.decide([])[0] == "fit"


def test_choose_survives_a_broken_video(monkeypatch):
    monkeypatch.setattr(gf, "measure", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no ffmpeg")))
    assert gf.choose("x.mp4", [{"start": 0, "end": 30}])[0] == "fit"


def test_web_framing_choice_becomes_a_flag_only_when_forced():
    assert web_args.game_args(True, "0.5") == ["--content", "game", "--game_mix", "0.5"]
    assert web_args.game_args(True, "0.5", "auto") == ["--content", "game", "--game_mix", "0.5"]
    assert web_args.game_args(True, "0.5", "crop")[-2:] == ["--game_framing", "crop"]
    assert web_args.game_args(True, "0.5", "fit")[-2:] == ["--game_framing", "fit"]
    assert web_args.game_args(False, "0.5", "crop") == []
