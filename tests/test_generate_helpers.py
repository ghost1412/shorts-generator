import json
import types

import engine.modes.generate as gen


def _args(**kw):
    base = dict(persona=None, cartoon=False, video_id=None, user_id=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_ensure_dict_normalises_llm_metadata():
    assert gen.ensure_dict(None) == {"title": "Viral Short", "description": "", "tags": []}
    out = gen.ensure_dict([{"title": "T", "description": ["a", "b"]}])
    assert out == {"title": "T", "description": "a\nb"}
    assert gen.ensure_dict({"title": 0, "description": 5}) == {"title": "Viral Short", "description": "5"}


def test_resolve_avatar_defaults_news_to_mafia_cat_and_prefers_video(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets" / "avatars").mkdir(parents=True)
    for n in ("mafia_cat.png", "mafia_cat.mp4", "robot.png"):
        (tmp_path / "assets" / "avatars" / n).write_bytes(b"x")
    assert gen.resolve_avatar(_args(), "FACTS") == (None, None)
    assert gen.resolve_avatar(_args(), "NEWS") == ("mafia_cat", "assets/avatars/mafia_cat.mp4")
    assert gen.resolve_avatar(_args(persona="robot"), "FACTS") == ("robot", "assets/avatars/robot.png")


def test_resolve_avatar_warns_when_persona_has_no_art(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    assert gen.resolve_avatar(_args(persona="superhero"), "STORY") == ("superhero", None)
    assert "no avatar file" in capsys.readouterr().out


def test_persist_and_export_writes_sidecars_without_a_dashboard_job(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    out = str(tmp_path / "short_1.mp4")
    meta = {"title": "Hello", "description": "d", "tags": ["a", "b"]}
    gen.persist_and_export(_args(), "FACTS", "space exploration", meta, out, out, "sid", None)
    assert "Title: Hello" in (tmp_path / "short_1.mp4.txt").read_text(encoding="utf-8")
    pkg = json.loads((tmp_path / "short_1.mp4.meta.json").read_text(encoding="utf-8"))
    assert pkg["mode"] == "FACTS" and "#spaceexploration" in pkg["tiktok"]["hashtags"]
