from engine import script_gen, social_gen

SEGS = [{"start": 0, "end": 5, "text": "Prices doubled last year."},
        {"start": 5, "end": 10, "text": "Nobody saw it coming."},
        {"start": 50, "end": 55, "text": "Unrelated."}]


def test_clip_transcript_text_only_overlapping_segments():
    assert social_gen.clip_transcript_text(SEGS, 3, 12) == "Prices doubled last year. Nobody saw it coming."


def test_generate_clip_metadata_uses_llm(monkeypatch):
    monkeypatch.setattr(script_gen, "get_llm_response",
                        lambda *a, **k: '{"title": "Why prices doubled", "description": "d", "tags": ["prices"]}')
    meta = social_gen.generate_clip_metadata("Prices doubled last year.", hook="x")
    assert meta["title"] == "Why prices doubled" and meta["tags"] == ["prices"]


def test_generate_clip_metadata_falls_back_when_llm_down(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("all providers failed")
    monkeypatch.setattr(script_gen, "get_llm_response", boom)
    meta = social_gen.generate_clip_metadata("Prices doubled last year. More.", hook="Prices doubled")
    assert meta["title"] == "Prices doubled" and "#shorts" in meta["description"]


def test_empty_transcript_uses_hook():
    assert social_gen.generate_clip_metadata("", hook="Big claim")["title"] == "Big claim"
