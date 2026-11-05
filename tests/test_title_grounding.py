"""A clip's main title and description must not say what the clip does not (offline, with a fake LLM)."""
import json

from engine import social_gen, title_variants

TEXT = ("So we tested the battery for three days and it lost only twelve percent. Honestly the charging speed surprised me, "
        "forty five minutes to full on the Pixel.")


def fake_llm(*replies):
    """An LLM that answers with each reply in turn (the last one repeats) and remembers the prompts."""
    calls = []

    def ask(prompt, **kw):
        calls.append(prompt)
        return replies[min(len(calls) - 1, len(replies) - 1)]
    ask.calls = calls
    return ask


def meta(title, description="Is this the best battery? #battery #tech", variants=None):
    return json.dumps({"title": title, "description": description, "tags": ["battery"], "title_variants": variants or []})


def test_grounding_problems_flags_unsaid_numbers_and_names_and_allows_sources():
    assert title_variants.grounding_problems("Battery lost only 12 percent", TEXT) == []                 # twelve = 12
    assert title_variants.grounding_problems("It lost 90 percent in a day", TEXT)                          # 90 is never said
    assert any("Samsung" in p for p in title_variants.grounding_problems("Why the Samsung beat it", TEXT))
    assert title_variants.grounding_problems("Why the Samsung beat it", TEXT, extra_sources=("Samsung test",)) == []   # the user's own note allows it


def test_a_grounded_title_needs_no_rewrite_and_no_second_request():
    ask = fake_llm(meta("Lost only twelve percent in three days"))
    out = social_gen.generate_clip_metadata(TEXT, hook="Twelve percent in three days", ask=ask)
    assert out["title"] == "Lost only twelve percent in three days" and len(ask.calls) == 1


def test_an_invented_number_gets_one_rewrite_request_naming_the_problem():
    ask = fake_llm(meta("Phone lost 90 percent overnight"), json.dumps({"title": "Lost only twelve percent in three days", "description": "Real battery test #battery"}))
    out = social_gen.generate_clip_metadata(TEXT, hook=None, ask=ask)
    assert out["title"] == "Lost only twelve percent in three days" and out["description"].startswith("Real battery test")
    assert len(ask.calls) == 2 and "90" in ask.calls[1] and "does not say" in ask.calls[1]


def test_if_the_rewrite_still_invents_something_the_title_falls_back_to_the_hook():
    ask = fake_llm(meta("Phone lost 90 percent overnight"), json.dumps({"title": "Galaxy S99 destroys it", "description": "x"}))
    out = social_gen.generate_clip_metadata(TEXT, hook="Charging speed surprised me", ask=ask)
    assert out["title"] == "Charging speed surprised me"


def test_an_invented_description_sentence_is_dropped_but_the_hashtags_are_kept():
    ask = fake_llm(meta("Lost only twelve percent", description="Apple admits 500 units failed. #battery #pixel"), "not json")
    out = social_gen.generate_clip_metadata(TEXT, hook="Twelve percent", ask=ask)
    assert "500" not in out["description"] and "Apple" not in out["description"]
    assert "#battery" in out["description"] and "#pixel" in out["description"]


def test_hashtags_alone_are_not_treated_as_claims():
    ask = fake_llm(meta("Lost only twelve percent", description="Is the battery really that good?\n#Samsung #Pixel #tech"))
    out = social_gen.generate_clip_metadata(TEXT, hook="Twelve percent", ask=ask)
    assert out["description"].startswith("Is the battery") and len(ask.calls) == 1
