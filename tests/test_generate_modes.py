"""Offline tests for the idea-to-video script generators: a stubbed LLM, and no Hugging Face key at all.

WYR, REDDIT, TRIVIA and QUOTE used to refuse to run without HF_API_KEY even though they use the generic provider chain
(Gemini / Groq / Ollama / HF), so they failed on any machine that had a working LLM but no Hugging Face token.
"""
import json

import pytest

import engine.script_gen as sg

LONG = " ".join(["word"] * 40)

GOOD = {
    "generate_wyr": ({"option_a": "Eat soup with a fork forever", "option_b": "Wear wet socks forever", "percent_a": 60, "percent_b": 30}, ()),
    "generate_trivia": ({"question": "Which planet has the most moons?", "answer": "Saturn", "options": ["Saturn", "Mars"]}, ()),
    "generate_quote": ({"quote": "The obstacle is the way forward for anyone", "author": "Marcus"}, ()),
    "generate_reddit_story": ({"title": "AITA for eating lunch", "story": LONG}, ()),
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


def test_wyr_percentages_are_forced_to_sum_to_100(monkeypatch):
    monkeypatch.setattr(sg, "get_llm_response", lambda *a, **k: json.dumps(GOOD["generate_wyr"][0]))
    out = sg.generate_wyr("food")
    assert out["percent_a"] + out["percent_b"] == 100


def test_llm_failure_propagates_so_the_run_stops_instead_of_posting_junk(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("All configured LLM providers failed.")
    monkeypatch.setattr(sg, "get_llm_response", boom)
    with pytest.raises(RuntimeError):
        sg.generate_trivia("history")
