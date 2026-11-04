"""Dubbing: script-aware burned-in captions and per-language voice choices."""
import json
import os

import pytest

from engine import dubbing


@pytest.fixture
def transcript(tmp_path):
    data = {"language": "en", "segments": [{"start": 0.0, "end": 2.0, "text": "Hello there", "words": []},
                                           {"start": 3.0, "end": 5.0, "text": "Welcome", "words": []}]}
    path = tmp_path / "t.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _fake_media(monkeypatch):
    monkeypatch.setattr(dubbing, "media_duration", lambda p: 1.0)


def test_voice_choices_and_override():
    assert dubbing.voice_for("es") == "es-ES-ElviraNeural"
    assert dubbing.voice_for("es", "female") == "es-ES-ElviraNeural" and dubbing.voice_for("es", "auto") == "es-ES-ElviraNeural"
    assert dubbing.voice_for("es", "male") == "es-ES-AlvaroNeural"
    assert dubbing.voice_for("pt_BR", "MALE") == "pt-BR-AntonioNeural"
    assert dubbing.voice_for("es", "es-MX-JorgeNeural") == "es-MX-JorgeNeural"
    assert dubbing.voice_for("xx", "male") is None
    with pytest.raises(ValueError):
        dubbing.voice_for("es", "not a voice")
    assert set(dubbing.EDGE_VOICES_MALE) == set(dubbing.EDGE_VOICES)
    every = list(dubbing.EDGE_VOICES.values()) + list(dubbing.EDGE_VOICES_MALE.values())
    assert all(dubbing.VOICE_NAME_RE.match(v) for v in every)


def test_bad_voice_fails_before_any_work(tmp_path):
    def boom():
        raise AssertionError("must not transcribe")
    with pytest.raises(ValueError, match="Unknown voice"):
        dubbing.dub_video("clip.mp4", "es", str(tmp_path), voice="nope", transcribe=boom)


def test_voice_reaches_the_synthesiser(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    monkeypatch.setattr(dubbing, "_parse", json.loads)
    llm = lambda prompt: json.dumps({"translations": [{"id": 0, "text": "Hola"}, {"id": 1, "text": "Adios"}]})  # noqa: E731
    calls = []

    def fake_edge_synth(text, lang, out, provider="auto", voice=None):
        calls.append((lang, voice))
        open(out, "wb").write(b"x")
        return out

    monkeypatch.setattr(dubbing, "synthesize", fake_edge_synth)
    dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, voice="male",
                      mixer=lambda src, clips, out, d, burn_srt=None: open(out, "wb").write(b"v"))
    assert calls and all(c == ("es", "male") for c in calls)


def test_ass_captions_name_a_font_for_each_script(monkeypatch):
    monkeypatch.setattr("engine.script_fonts.cjk_subset", lambda text, hint=None, **k: None)
    segs = [{"start": 0.0, "end": 2.0, "text": "Hello नमस्ते world"},
            {"start": 2.0, "end": 4.0, "text": "مرحبا بكم"},
            {"start": 4.0, "end": 6.0, "text": "Привет мир {x}"}]
    ass = dubbing.build_ass(segs, size=(1080, 1920))
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    # case kept; only the Devanagari word is retagged (scaled up) and the style is restored for the next word
    assert "Hello {\\fnNoto Sans Devanagari\\fscx118\\fscy118}नमस्ते{\\r} world" in ass
    assert "{\\fnNoto Sans Arabic\\fscx120\\fscy120}مرحبا{\\r} {\\fnNoto Sans Arabic\\fscx120\\fscy120}بكم{\\r}" in ass
    assert "{\\fnNoto Sans}Привет{\\r} {\\fnNoto Sans}мир{\\r} x" in ass   # braces stripped (they would open an ASS tag)
    assert "Dialogue: 0,0:00:02.00,0:00:04.00" in ass


def test_ass_captions_use_the_cjk_subset_font(monkeypatch):
    monkeypatch.setattr("engine.script_fonts.cjk_subset", lambda text, hint=None, **k: ("SFCJK-ja-12345678", "x.ttf"))
    ass = dubbing.build_ass([{"start": 0, "end": 1, "text": "こんにちは世界"}])
    assert "{\\fnSFCJK-ja-12345678}こんにちは世界" in ass


def test_long_cjk_lines_are_cut_to_fit_the_frame(monkeypatch):
    monkeypatch.setattr("engine.script_fonts.cjk_subset", lambda text, hint=None, **k: ("SFCJK-ja-12345678", "x.ttf"))
    text = "こんにちは世界" * 5  # 35 characters, no spaces
    ass = dubbing.build_ass([{"start": 0, "end": 1, "text": text}], size=(720, 1280))
    body = ass.split("Default,,0,0,0,,")[1]
    pieces = body.strip().split("\\N")
    assert len(pieces) >= 3 and all(p.startswith("{\\fnSFCJK-ja-12345678}") for p in pieces)
    assert "".join(p.replace("{\\fnSFCJK-ja-12345678}", "").replace("{\\r}", "") for p in pieces) == text
    short = dubbing.build_ass([{"start": 0, "end": 1, "text": "こんにちは"}], size=(720, 1280))
    assert "\\N" not in short.split("Dialogue:")[1]


def test_dub_video_writes_an_ass_next_to_the_srt_when_captions_are_on(tmp_path, monkeypatch, transcript):
    _fake_media(monkeypatch)
    monkeypatch.setattr(dubbing, "_parse", json.loads)
    llm = lambda prompt: json.dumps({"translations": [{"id": 0, "text": "Hola"}, {"id": 1, "text": "Bienvenido"}]})  # noqa: E731
    mixer = lambda src, clips, out, d, burn_srt=None: open(out, "wb").write(b"v")  # noqa: E731
    synth = lambda text, out: open(out, "wb").write(b"x")  # noqa: E731
    res = dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: transcript, llm=llm, synth=synth,
                            mixer=mixer, captions=True)
    ass = res["srt"][:-4] + ".ass"
    assert os.path.exists(ass) and "Bienvenido" in open(ass, encoding="utf-8").read()
    res2 = dubbing.dub_video("clip.mp4", "es", str(tmp_path / "b"), transcribe=lambda: transcript, llm=llm, synth=synth,
                             mixer=mixer, captions=False)
    assert not os.path.exists(res2["srt"][:-4] + ".ass")


def test_mix_dub_burns_the_ass_with_staged_fonts(tmp_path, monkeypatch):
    monkeypatch.setattr(dubbing, "media_duration", lambda p: 5.0)
    monkeypatch.setattr(dubbing, "has_audio", lambda p: True)
    (tmp_path / "v.mp4").write_bytes(b"v")
    (tmp_path / "c.mp3").write_bytes(b"a")
    (tmp_path / "v_es.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHola\n", encoding="utf-8")
    (tmp_path / "v_es.ass").write_text("[Script Info]\n", encoding="utf-8")
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["cwd"] = cmd, kw.get("cwd")
        open(cmd[-1], "wb").write(b"out")
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(dubbing.subprocess, "run", fake_run)
    clips = [{"path": str(tmp_path / "c.mp3"), "start": 0.0, "tempo": 1.0, "trim": None}]
    dubbing.mix_dub(str(tmp_path / "v.mp4"), clips, str(tmp_path / "out.mp4"), str(tmp_path),
                    burn_srt=str(tmp_path / "v_es.srt"))
    vf = seen["cmd"][seen["cmd"].index("-vf") + 1]
    assert vf == "ass=v_es.ass:fontsdir=." and seen["cwd"] == str(tmp_path)
    assert (tmp_path / "NotoSansArabic.ttf").exists()  # the bundled fonts were copied next to the .ass


def test_video_size_falls_back_for_a_missing_file():
    assert dubbing.video_size("does_not_exist.mp4") == (1280, 720)
    assert dubbing.video_size("does_not_exist.mp4", default=(1, 2)) == (1, 2)
