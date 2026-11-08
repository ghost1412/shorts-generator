import json
import os

from engine import puzzle_variety as pv
from engine import script_gen, sound_pack


def make_pack(tmp_path, entries):
    for name, e in entries.items():
        (tmp_path / e["file"]).write_bytes(b"x")
    (tmp_path / "manifest.json").write_text(json.dumps({k: v for k, v in entries.items()}), encoding="utf-8")
    return str(tmp_path)


def entry(file, lic="CC0", db=-20.0, author=""):
    return {"file": file, "title": file, "license": lic, "author": author, "source": "https://commons.wikimedia.org/wiki/File:" + file, "mean_db": db}


def test_load_skips_missing_and_silent(tmp_path):
    d = make_pack(tmp_path, {"cat": entry("cat.mp3"), "dog": entry("dog.mp3", db=-80.0)})
    (tmp_path / "gone.mp3").unlink(missing_ok=True)
    assert sound_pack.labels(d) == ["cat"]


def test_match_prefers_longest_label(tmp_path):
    d = make_pack(tmp_path, {"car": entry("car.mp3"), "car horn": entry("horn.mp3")})
    assert sound_pack.match("old car horn honk", d) == "car horn"
    assert sound_pack.match("unrelated", d) is None


def test_credit_only_for_attribution_licences(tmp_path):
    d = make_pack(tmp_path, {"cat": entry("cat.mp3"), "dog": entry("dog.mp3", lic="CC BY-SA 4.0", author="Someone")})
    assert sound_pack.credit("cat", d) == ""
    assert "CC BY-SA 4.0" in sound_pack.credit("dog", d) and "Someone" in sound_pack.credit("dog", d)


def test_challenge_answer_is_always_a_bundled_sound(tmp_path, monkeypatch):
    d = make_pack(tmp_path, {"cat": entry("cat.mp3"), "dog": entry("dog.mp3")})
    monkeypatch.setattr(sound_pack, "DIR", d)
    monkeypatch.setattr(pv, "_path", lambda: str(tmp_path / "h.json"))
    got = script_gen.generate_sound_challenge()
    assert got["object"] in ("cat", "dog") and got["object"] in got["reveal_text"]
    assert sound_pack.path(got["sound_query"], d)
