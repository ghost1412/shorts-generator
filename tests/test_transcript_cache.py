import json

from engine import transcript_cache as tc


def _video(tmp_path, name="v.mp4", data=b"A" * 3000):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def _transcript(path, text="hello"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"segments": [{"start": 0, "end": 1, "text": text, "words": []}], "source_video_path": "old"}, f)


def test_key_depends_on_video_language_fillers_and_model(tmp_path):
    v = _video(tmp_path)
    base = tc.cache_key(v, "en", False, "medium")
    assert base == tc.cache_key(v, "EN", False, "medium")
    assert base != tc.cache_key(v, "es", False, "medium")
    assert base != tc.cache_key(v, "en", True, "medium")
    assert base != tc.cache_key(v, "en", False, "small")
    other = _video(tmp_path, "w.mp4", b"B" * 3000)
    assert base != tc.cache_key(other, "en", False, "medium")
    assert tc.cache_key(str(tmp_path / "missing.mp4"), "en", False, "medium") is None


def test_the_same_content_under_another_path_has_the_same_key(tmp_path):
    a = _video(tmp_path, "a.mp4", b"X" * 5_000_000)
    b = tmp_path / "sub"
    b.mkdir()
    c = _video(b, "copy.mp4", b"X" * 5_000_000)
    assert tc.cache_key(a, "en", False, "m") == tc.cache_key(c, "en", False, "m")


def test_store_lookup_restore_roundtrip(tmp_path):
    v = _video(tmp_path)
    key = tc.cache_key(v, "en", False, "medium")
    assert tc.lookup(key) is None
    src = tmp_path / "s1" / "transcript.json"
    src.parent.mkdir()
    _transcript(str(src))
    assert tc.store(key, str(src))
    hit = tc.lookup(key)
    assert hit
    new = tmp_path / "s2" / "transcript.json"
    assert tc.restore(hit, str(new), v)
    data = json.loads(new.read_text(encoding="utf-8"))
    assert data["segments"][0]["text"] == "hello"
    assert data["source_video_path"].endswith("v.mp4") and data["source_video_path"] != "old"     # points at this run's video


def test_empty_or_broken_transcripts_are_not_cached_or_restored(tmp_path):
    key = "abc"
    bad = tmp_path / "t.json"
    bad.write_text(json.dumps({"segments": []}), encoding="utf-8")
    assert not tc.store(key, str(bad))
    bad.write_text("{nope", encoding="utf-8")
    assert not tc.store(key, str(bad))
    assert not tc.restore(str(bad), str(tmp_path / "x.json"), "v.mp4")
    assert tc.store(None, str(bad)) is False and tc.lookup(None) is None


def test_it_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_TRANSCRIPT_CACHE", "off")
    assert not tc.enabled()
    monkeypatch.setenv("SHORTSFLOW_TRANSCRIPT_CACHE", "on")
    assert tc.enabled()


def test_second_session_reuses_the_transcript_without_running_the_speech_model(tmp_path, monkeypatch):
    import sys
    import types
    from engine import analysis

    calls = {"n": 0}

    class FakeModel:
        def transcribe(self, path, language=None, initial_prompt=None):
            calls["n"] += 1
            return {"segments": [{"start": 0.0, "end": 2.0, "text": "hi there", "words": []}], "language": "en"}

    fake_whisper = types.SimpleNamespace(load_model=lambda name, device=None: FakeModel())
    fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "stable_whisper", fake_whisper)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    video = _video(tmp_path)

    first = analysis.transcribe_video(video, str(tmp_path / "session1"), language="en")
    assert calls["n"] == 1 and json.load(open(first, encoding="utf-8"))["segments"][0]["text"] == "hi there"
    second = analysis.transcribe_video(video, str(tmp_path / "session2"), language="en")
    assert calls["n"] == 1                                              # not transcribed again
    assert json.load(open(second, encoding="utf-8"))["segments"][0]["text"] == "hi there"
    analysis.transcribe_video(video, str(tmp_path / "session3"), language="es")
    assert calls["n"] == 2                                              # another language is another transcript
