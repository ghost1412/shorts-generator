import json

import pytest

from engine import caption_translate as ct


def _transcript(tmp_path, language="en"):
    data = {"language": language, "text": "hello there friend. goodbye", "segments": [
        {"start": 1.0, "end": 3.0, "text": " hello there friend.",
         "words": [{"word": " hello", "start": 1.0, "end": 1.5}, {"word": " there", "start": 1.5, "end": 2.2}, {"word": " friend.", "start": 2.2, "end": 3.0}]},
        {"start": 4.0, "end": 5.0, "text": " goodbye", "words": [{"word": " goodbye", "start": 4.0, "end": 5.0}]},
    ]}
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_resolve_language_accepts_codes_and_names_and_rejects_unsupported_scripts():
    assert ct.resolve_language("ES") == "es" and ct.resolve_language("Hindi") == "hi"
    assert [ct.resolve_language(x) for x in ("ja", "Chinese", "korean", "ar")] == ["ja", "zh", "ko", "ar"]
    with pytest.raises(ValueError, match="not supported"):
        ct.resolve_language("th")


def test_caption_tokens_cut_unspaced_languages_into_short_chunks():
    assert ct.caption_tokens("hola amigo mío") == ["hola", "amigo", "mío"]
    assert ct.caption_tokens("مرحبا بالعالم") == ["مرحبا", "بالعالم"]
    assert ct.caption_tokens("안녕하세요 여러분") == ["안녕하세요", "여러분"]
    tokens = ct.caption_tokens("今天我们来聊聊人工智能，好吗？")
    assert "".join(tokens) == "今天我们来聊聊人工智能，好吗？"
    assert all(len(t) <= 4 for t in tokens)
    assert any(t.endswith("，") for t in tokens)  # punctuation stays with the chunk before it
    assert ct.caption_tokens("使用AI工具") == ["使用", "AI", "工具"]


def test_respread_covers_the_original_span_in_order():
    seg = {"start": 1.0, "end": 3.0, "words": [{"word": " a", "start": 1.0, "end": 1.4}, {"word": " b", "start": 2.0, "end": 3.0}]}
    words = ct.respread(seg, "hola amigo mío")
    assert [w["word"].strip() for w in words] == ["hola", "amigo", "mío"]
    assert words[0]["start"] == 1.0 and abs(words[-1]["end"] - 3.0) < 0.01
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(words, words[1:]))


def test_translate_transcript_writes_a_translated_copy_and_keeps_timing(tmp_path):
    path = _transcript(tmp_path)
    out = ct.translate_transcript(path, "es", ask=lambda prompt: {"0": "hola amigo mío", "1": "adiós"})
    data = json.load(open(out, encoding="utf-8"))
    assert out.endswith("transcript_es.json") and data["language"] == "es"
    assert [w["word"].strip() for w in data["segments"][0]["words"]] == ["hola", "amigo", "mío"]
    assert data["segments"][1]["words"][0]["start"] == 4.0
    assert json.load(open(path))["language"] == "en"          # the original is untouched


def test_untranslated_segments_keep_their_original_words(tmp_path):
    path = _transcript(tmp_path)
    out = ct.translate_transcript(path, "fr", ask=lambda prompt: {"0": "bonjour mon ami"})   # the AI skipped segment 1
    data = json.load(open(out, encoding="utf-8"))
    assert data["segments"][1]["words"][0]["word"] == " goodbye"


def test_no_translation_when_the_video_is_already_in_that_language(tmp_path):
    path = _transcript(tmp_path, language="es")
    assert ct.translate_transcript(path, "es", ask=lambda prompt: pytest.fail("must not ask")) == path


def test_total_failure_is_reported_in_plain_words(tmp_path):
    path = _transcript(tmp_path)
    with pytest.raises(RuntimeError, match="could not be translated"):
        ct.translate_transcript(path, "de", ask=lambda prompt: (_ for _ in ()).throw(RuntimeError("no provider")))
