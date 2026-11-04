import json

from engine import script_gen, social_gen, title_variants as tv

TRANSCRIPT = ("Prices doubled last year in Berlin. Three landlords told me they raised rent by 40 percent. "
              "Nobody saw it coming, and Maria says it will get worse.")


def test_grounded_numbers_accept_digits_and_spelled_out():
    assert tv.ungrounded_numbers("3 landlords, 40% rent rises", TRANSCRIPT) == []
    assert tv.ungrounded_numbers("Rent up 90 percent", TRANSCRIPT) == ["90"]
    assert tv.ungrounded_numbers("Prices doubled", TRANSCRIPT) == []


def test_thousand_separator_matches_spelled_number():
    assert tv.ungrounded_numbers("1,000 landlords", "about one thousand landlords") == []


def test_ungrounded_names_flags_invented_names_only():
    assert tv.ungrounded_names("What Maria knows about Berlin", TRANSCRIPT) == []
    assert tv.ungrounded_names("Why Elon Musk is wrong", TRANSCRIPT) == ["Elon", "Musk"]
    # the first word and ordinary sentence starters are not names
    assert tv.ungrounded_names("Why this happened", TRANSCRIPT) == []


def test_parse_variants_drops_ungrounded_duplicate_and_long():
    raw = [
        {"style": "curiosity", "title": "The rent secret Berlin hides"},
        {"style": "number", "title": "Rent up 90 percent in Berlin"},          # 90 is invented
        {"style": "question", "title": "Why did Prices doubled in Paris?"},    # Paris is invented
        {"style": "question", "title": "Why did prices double?"},
        {"style": "curiosity", "title": "x" * 90},                              # too long
    ]
    out = tv.parse_variants(raw, TRANSCRIPT, base_title="Prices doubled")
    assert [v["title"] for v in out] == ["The rent secret Berlin hides", "Why did prices double?"]
    assert out[0]["style"] == "curiosity" and out[1]["style"] == "question"


def test_parse_variants_skips_main_title_and_accepts_strings():
    out = tv.parse_variants(["Prices doubled", "Nobody saw it coming"], TRANSCRIPT, base_title="Prices doubled!")
    assert [v["title"] for v in out] == ["Nobody saw it coming"]
    assert out[0]["style"] in tv.STYLES


def test_parse_variants_ignores_junk():
    assert tv.parse_variants(None, TRANSCRIPT) == []
    assert tv.parse_variants("a string", TRANSCRIPT) == []
    assert tv.parse_variants([None, {}, 5], TRANSCRIPT) == []


def test_hook_counts_as_a_source():
    out = tv.parse_variants(["Inside the Acme tactic"], TRANSCRIPT, base_title="t", hook="Acme tactic revealed")
    assert [v["title"] for v in out] == ["Inside the Acme tactic"]


def test_variants_text():
    text = tv.variants_text([{"style": "number", "title": "3 landlords"}, {"style": "question", "title": "Why?"}])
    assert text == "[Number] 3 landlords\n[Question] Why?"
    assert tv.variants_text(None) == ""


def _llm(payload):
    return lambda *a, **k: json.dumps(payload)


def test_generate_clip_metadata_keeps_only_grounded_variants(monkeypatch):
    payload = {"title": "Why prices doubled", "description": "d", "tags": ["rent"], "title_variants": [
        {"style": "curiosity", "title": "What landlords will not tell you"},
        {"style": "number", "title": "40 percent rent rises, says Maria"},
        {"style": "question", "title": "Is Hamburg next?"},
    ]}
    monkeypatch.setattr(script_gen, "get_llm_response", _llm(payload))
    meta = social_gen.generate_clip_metadata(TRANSCRIPT, hook="x")
    assert meta["title"] == "Why prices doubled"            # existing fields unchanged
    assert meta["tags"] == ["rent"] and meta["description"] == "d"
    assert [v["title"] for v in meta["title_variants"]] == ["What landlords will not tell you", "40 percent rent rises, says Maria"]


def test_generate_clip_metadata_without_variants_gives_empty_list(monkeypatch):
    monkeypatch.setattr(script_gen, "get_llm_response", _llm({"title": "T", "description": "d", "tags": []}))
    assert social_gen.generate_clip_metadata(TRANSCRIPT)["title_variants"] == []


def test_fallback_metadata_has_empty_variants(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(script_gen, "get_llm_response", boom)
    assert social_gen.generate_clip_metadata(TRANSCRIPT, hook="h")["title_variants"] == []
    assert social_gen.generate_clip_metadata("", hook="h")["title_variants"] == []


def test_review_cards_and_zip_carry_variants(tmp_path):
    import zipfile
    from shortsflow import review
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x" * 10)
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"clips": [{"clip_index": 1, "video_path": str(video), "title": "T", "title_variants": [
        {"style": "curiosity", "title": "A teaser"}, "junk", {"style": "number"}]}]}), encoding="utf-8")
    cards = review.load_results(str(results))
    assert cards[0]["title_variants"] == [{"style": "curiosity", "title": "A teaser"}]
    assert review.variants_text(cards[0]) == "[Curiosity] A teaser"
    z = review.build_zip(cards, str(tmp_path / "out.zip"))
    with zipfile.ZipFile(z) as zf:
        txt = [n for n in zf.namelist() if n.endswith(".txt")][0]
        assert "Other title ideas:\n[Curiosity] A teaser" in zf.read(txt).decode("utf-8")


def test_old_results_without_variants_still_load(tmp_path):
    from shortsflow import review
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"clips": [{"clip_index": 1, "video_path": str(video), "title": "T"}]}), encoding="utf-8")
    card = review.load_results(str(results))[0]
    assert card["title_variants"] == [] and review.variants_text(card) == ""
