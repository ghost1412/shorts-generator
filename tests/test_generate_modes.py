"""Offline tests for the idea-to-video script generators: a stubbed LLM, and no Hugging Face key at all.

WYR, REDDIT, TRIVIA and QUOTE used to refuse to run without HF_API_KEY even though they use the generic provider chain
(Gemini / Groq / Ollama / HF), so they failed on any machine that had a working LLM but no Hugging Face token.
"""
import json

import pytest

import engine.script_gen as sg

LONG = " ".join(["word"] * 40)

GOOD = {
    "generate_wyr": ({"option_a": "Eat soup with a fork forever", "option_b": "Wear wet socks forever"}, ()),
    "generate_trivia": ({"question": "Which planet has the most moons?", "answer": "Saturn", "options": ["Saturn", "Mars"]}, ()),
    "generate_quote": ({"quote": "The obstacle is the way forward for anyone", "author": "Marcus"}, ()),
    "generate_reddit_story": ({"title": "AITA for eating lunch", "story": LONG + " AITA?"}, ()),
    "generate_story": ({"title": "The last lighthouse", "story": LONG}, ()),
}
BAD = {
    "generate_wyr": {"option_a": "only one option"},
    "generate_trivia": {"question": "no answer"},
    "generate_quote": {"quote": "too short", "author": "x"},
    "generate_reddit_story": {"title": "short story", "story": "far too few words"},
    "generate_story": {"title": "short story", "story": "far too few words"},
}


@pytest.fixture(autouse=True)
def no_hf_key(monkeypatch):
    monkeypatch.setattr(sg, "HF_API_KEY", None)


@pytest.mark.parametrize("name", sorted(GOOD))
def test_generator_works_without_a_huggingface_key(name, monkeypatch):
    data, args = GOOD[name]
    monkeypatch.setattr(sg, "get_llm_response", lambda prompt, *a, **k: json.dumps(data))
    out = getattr(sg, name)("science", *args)
    assert out and all(out.get(k) is not None for k in data if k in ("title", "question", "quote", "option_a"))


@pytest.mark.parametrize("name", sorted(GOOD))
def test_generator_retries_an_invalid_reply_then_succeeds(name, monkeypatch):
    replies = iter([json.dumps(BAD[name]), json.dumps(GOOD[name][0])])
    calls = []
    monkeypatch.setattr(sg, "get_llm_response", lambda prompt, *a, **k: (calls.append(1), next(replies))[1])
    out = getattr(sg, name)("science")
    assert len(calls) == 2 and out


@pytest.mark.parametrize("name", sorted(GOOD))
def test_generator_gives_up_after_three_invalid_replies(name, monkeypatch):
    monkeypatch.setattr(sg, "get_llm_response", lambda prompt, *a, **k: json.dumps(BAD[name]))
    with pytest.raises(Exception):
        getattr(sg, name)("science")


def test_wyr_makes_up_no_vote_percentages(monkeypatch):
    monkeypatch.setattr(sg, "get_llm_response", lambda *a, **k: json.dumps(GOOD["generate_wyr"][0]))
    out = sg.generate_wyr("food")
    assert out["option_a"]


def test_llm_failure_propagates_so_the_run_stops_instead_of_posting_junk(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("All configured LLM providers failed.")
    monkeypatch.setattr(sg, "get_llm_response", boom)
    with pytest.raises(RuntimeError):
        sg.generate_trivia("history")


@pytest.mark.parametrize("line", [
    "Tie your trembling fingers to the steering wheel and drive straight into the sun.",
    "Some days the only way out is to end it all and start over again.",
    "You cannot hurt yourself into becoming a better person than you were.",
    "Do not wait for death to teach you what the living already know well.",
])
def test_quotes_about_harm_death_or_danger_are_rejected(line):
    assert sg.validate_quote({"quote": line, "author": "Unknown"}) is False


@pytest.mark.parametrize("line", [
    "A small step taken today is worth more than a perfect plan tomorrow.",
    "Your deadline is not the enemy; waiting to begin is.",
    "Patience is a skill you build by finishing slow things, one afternoon at a time.",
])
def test_ordinary_quotes_still_pass(line):
    assert sg.validate_quote({"quote": line, "author": "Unknown"}) is True


def test_one_word_captions_never_overlap_the_next_word():
    from engine.video_gen import word_display_seconds as show
    assert show(10.0, 0.25, 10.25) == pytest.approx(0.25)          # fast speech: gone when the next word starts
    assert show(10.0, 0.25, 10.12) == pytest.approx(0.12)
    assert show(10.0, 0.25, 10.01) == pytest.approx(0.1)           # never shorter than the floor
    assert show(10.0, 0.25, None) == pytest.approx(0.6)            # the last word stays long enough to read
    assert show(10.0, 0.9, 12.0) == pytest.approx(0.9)             # a slow word keeps its own length
    assert show(10.0, 0.25, 9.0) == pytest.approx(0.6)             # timings out of order: leave it alone


def test_horror_and_true_crime_use_their_own_title_on_screen():
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "engine", "modes", "generate.py"), encoding="utf-8").read()
    assert 'mode == "HORROR" and \'horror_data\' in locals()' in src and "horror_data[\"title\"]" in src
    assert src.index('mode == "HORROR" and \'horror_data\'') < src.index("render_title = category.replace")   # before the category fallback
