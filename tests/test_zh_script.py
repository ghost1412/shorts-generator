import json

import pytest

from engine import zh_script as zh

# a tiny stand-in for OpenCC so the tests do not need the package
_T2S = {"我們": "我们", "來": "来", "變": "变", "學習": "学习"}


def fake_t2s(text):
    for k, v in _T2S.items():
        text = text.replace(k, v)
    return text


def _transcript(tmp_path, text="我們來學習", language="zh"):
    data = {"language": language, "text": text, "segments": [
        {"start": 1.0, "end": 3.0, "text": " " + text,
         "words": [{"word": " 我們", "start": 1.0, "end": 1.5, "probability": 0.9},
                   {"word": "來", "start": 1.5, "end": 2.0}, {"word": "學習", "start": 2.0, "end": 3.0},
                   {"word": " OK", "start": 3.0, "end": 3.2}]}]}
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path), data


def test_resolve_script_accepts_aliases_and_rejects_others():
    assert zh.resolve_script(None) == "auto" and zh.resolve_script("") == "auto"
    assert [zh.resolve_script(x) for x in ("Simplified", "zh-CN", "hans", "S")] == ["simplified"] * 4
    assert [zh.resolve_script(x) for x in ("traditional", "zh_TW", "Hant", "t")] == ["traditional"] * 4
    with pytest.raises(ValueError, match="--zh_script"):
        zh.resolve_script("pinyin")


def test_convert_text_leaves_auto_and_non_chinese_alone():
    assert zh.convert_text("我們來", "auto", fake_t2s) == "我們來"
    assert zh.convert_text("hello world", "simplified", fake_t2s) == "hello world"
    assert zh.convert_text("我們來", "simplified", fake_t2s) == "我们来"


def test_convert_transcript_converts_text_and_words_but_keeps_timing(tmp_path):
    path, original = _transcript(tmp_path)
    out = zh.convert_transcript(path, "simplified", convert=fake_t2s)
    assert out != path and out.endswith("transcript_simplified.json")
    data = json.load(open(out, encoding="utf-8"))
    seg = data["segments"][0]
    assert data["text"] == "我们来学习" and seg["text"] == " 我们来学习"
    assert [w["word"] for w in seg["words"]] == [" 我们", "来", "学习", " OK"]
    assert [(w["start"], w["end"]) for w in seg["words"]] == [(w["start"], w["end"]) for w in original["segments"][0]["words"]]
    assert seg["words"][0]["probability"] == 0.9
    assert json.load(open(path, encoding="utf-8")) == original  # the original transcript is not touched


def test_convert_transcript_auto_and_no_chinese_return_the_original_path(tmp_path):
    path, _ = _transcript(tmp_path)
    assert zh.convert_transcript(path, "auto", convert=fake_t2s) == path
    english, _ = _transcript(tmp_path, text="hello there", language="en")
    assert zh.convert_transcript(english, "traditional", convert=fake_t2s) == english


def test_without_opencc_the_run_goes_on_with_a_clear_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(zh, "_converter", lambda script: None)
    path, _ = _transcript(tmp_path)
    assert zh.convert_transcript(path, "simplified") == path
    assert 'pip install "shortsflow[zh]"' in capsys.readouterr().out
    with pytest.raises(RuntimeError, match=r"shortsflow\[zh\]"):
        zh.convert_text("我們", "simplified")
    highlights = [{"hook_text": "我們來"}]
    assert zh.convert_highlights(highlights, "simplified") == [{"hook_text": "我們來"}]


def test_convert_highlights_converts_the_texts_in_place():
    highlights = [{"hook_text": "我們來", "reason": "學習 tips", "start": 1.0}]
    zh.convert_highlights(highlights, "simplified", convert=fake_t2s)
    assert highlights == [{"hook_text": "我们来", "reason": "学习 tips", "start": 1.0}]


def test_real_opencc_round_trip_when_installed():
    pytest.importorskip("opencc")
    assert zh.convert_text("我們來學習", "simplified") == "我们来学习"
    assert zh.convert_text("我们来学习", "traditional") == "我們來學習"
