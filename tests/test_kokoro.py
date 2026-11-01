from engine import kokoro_tts


def test_split_chunks_keeps_punctuation_and_drops_noise():
    assert kokoro_tts.split_chunks("Number one. Octopuses have three hearts, and blue blood!") == [
        ("Number one", "."), ("Octopuses have three hearts", ","), ("and blue blood", "!")]
    assert kokoro_tts.split_chunks("... ,, !") == []


def test_word_times_cover_the_chunk_in_order():
    words = kokoro_tts.word_times("Octopuses have three hearts", 2.0, 2.0)
    assert [w["word"] for w in words] == ["Octopuses", "have", "three", "hearts"]
    assert words[0]["start"] == 2.0 and abs(words[-1]["end"] - 4.0) < 0.01
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(words, words[1:]))
    assert words[0]["duration"] > words[1]["duration"]  # longer word gets longer
    assert kokoro_tts.word_times("", 0, 1) == []


def test_pick_voice(monkeypatch):
    monkeypatch.delenv("KOKORO_VOICE", raising=False)
    assert kokoro_tts.pick_voice("am_michael") == "am_michael"
    assert kokoro_tts.pick_voice("en-US-AvaNeural") == "af_heart"
    monkeypatch.setenv("KOKORO_VOICE", "bf_emma")
    assert kokoro_tts.pick_voice(None) == "bf_emma"


def test_unavailable_without_model_files(monkeypatch, tmp_path):
    monkeypatch.setenv("KOKORO_MODEL_DIR", str(tmp_path))
    assert kokoro_tts.is_available() is False
