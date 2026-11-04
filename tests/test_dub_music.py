import os

from engine import dubbing, stem_split

PL = [{"index": 1, "start": 1.0, "tempo": 1.0, "trim": None}]


def test_music_mode_uses_the_voice_free_stem():
    f = dubbing.build_filter(PL, 10, True, "music", stem_index=2)
    assert "[2:a]aresample=44100,volume=0.9[orig]" in f and "[0:a]" not in f


def test_music_mode_without_stem_falls_back_to_quiet():
    f = dubbing.build_filter(PL, 10, True, "music", stem_index=None)
    assert f"[0:a]aresample=44100,volume={dubbing.QUIET_GAIN}[orig]" in f


def test_other_modes_unchanged():
    assert "volume=" not in dubbing.build_filter(PL, 10, True, "duck").split("[orig]")[0].split(";")[-1]
    assert "[orig]" not in dubbing.build_filter(PL, 10, True, "mute")


def test_translation_prompt_carries_context_and_misheard_note():
    seen = []

    def llm(prompt):
        seen.append(prompt)
        return '{"translations": [{"id": 0, "text": "Kratos came."}]}'

    texts, failed = dubbing.translate_segments([{"start": 0, "end": 3, "text": "x"}], "en", llm=llm,
                                               parse=__import__("json").loads, about="God of War 3: Kratos, Zeus")
    assert texts == ["Kratos came."] and failed == 0
    assert "Kratos, Zeus" in seen[0] and "misheard" in seen[0]


def test_split_vocals_without_demucs_returns_none(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(stem_split, "available", lambda: False)
    assert stem_split.split_vocals("v.mp4", str(tmp_path)) is None
    assert "pip install demucs" in capsys.readouterr().out


def test_split_vocals_uses_cache(monkeypatch, tmp_path):
    p = tmp_path / "stems" / "htdemucs" / "voice_src"
    p.mkdir(parents=True)
    (p / "no_vocals.wav").write_bytes(b"x" * 2000)
    monkeypatch.setattr(stem_split, "available", lambda: False)      # would fail if it tried to separate again
    assert stem_split.split_vocals("v.mp4", str(tmp_path)) == os.path.join(str(tmp_path), "stems", "htdemucs", "voice_src", "no_vocals.wav")
