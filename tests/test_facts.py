import json

import pytest

import engine.script_gen as sg


def facts(*truths, words=6):
    return [{"fact": " ".join(["word"] * words), "truth": t} for t in truths]


@pytest.mark.parametrize("data, ok", [
    ({"hook": "h", "facts": facts(True, True, False)}, True),
    ({"hook": "h", "facts": facts(True, False, False)}, False),          # two lies
    ({"hook": "h", "facts": facts(True, True, True)}, False),            # no lie
    ({"hook": "h", "facts": facts(True, False)}, False),                 # only two facts
    ({"facts": facts(True, True, False)}, False),                        # no hook
    ({"hook": "h", "facts": facts(True, True, False, words=2)}, False),  # fact too short
    ({"hook": "h", "facts": facts(True, True, False, words=40)}, False), # fact too long
    ({"hook": "h", "facts": facts("true", True, False)}, False),         # truth must be bool
    ("not a dict", False),
])
def test_validate_mixed_facts(data, ok):
    assert sg.validate_mixed_facts(data) is ok


def test_generate_mixed_facts_coerces_and_retries(monkeypatch):
    bad = {"hook": "h", "facts": facts(True, True, True)}
    good = {"hook": "Rome had a strange rule", "facts": [
        {"fact": "Emperors declared war on the sea god Neptune once", "truth": "true"},
        {"fact": "Romans used crushed mouse brains as toothpaste", "truth": "True"},
        {"fact": "Caesar banned purple togas except for gladiators", "truth": "false"},
    ], "lie_explanation": "Purple was for emperors.", "loop_lead": "Rewatch."}
    replies = iter([json.dumps(bad), json.dumps(good)])
    monkeypatch.setattr(sg, "get_llm_response", lambda prompt, **kw: next(replies))

    out = sg.generate_mixed_facts("history")

    assert sum(f["truth"] is False for f in out["facts"]) == 1
    assert all(isinstance(f["truth"], bool) for f in out["facts"])


def test_generate_mixed_facts_shuffles_lie_position(monkeypatch):
    payload = json.dumps({"hook": "h", "facts": [
        {"fact": "first true fact about something odd", "truth": True},
        {"fact": "second true fact about something odd", "truth": True},
        {"fact": "the lie that sounds rather believable", "truth": False},
    ]})
    monkeypatch.setattr(sg, "get_llm_response", lambda prompt, **kw: payload)
    positions = {
        next(i for i, f in enumerate(sg.generate_mixed_facts("space")["facts"]) if not f["truth"])
        for _ in range(40)
    }
    assert len(positions) > 1


def test_unknown_category_is_used_as_topic():
    assert sg.get_sub_topic("ancient_civilizations") == "ancient civilizations"


def test_known_category_returns_its_own_sub_topics():
    for _ in range(20):
        assert sg.get_sub_topic("space") in [
            "exoplanets", "black holes", "moon landing secrets", "stellar phenomena",
            "alien life theories", "the edge of the universe", "rogue planets"]
