import json

import pytest

from engine import fact_check as fc

FACTS = {"hook": "h", "facts": [{"fact": "Octopuses have three hearts", "truth": True},
                                {"fact": "Honey never spoils in sealed jars", "truth": True},
                                {"fact": "Goldfish forget everything in three seconds", "truth": False}]}


def asker(reply):
    return lambda prompt: reply


def test_judge_agreeing_with_the_labels_keeps_the_script():
    assert fc.facts_ok(FACTS, asker('["true", "true", "false"]'))


def test_judge_disputing_a_true_fact_or_the_lie_rejects_it():
    assert not fc.facts_ok(FACTS, asker('["true", "unsure", "false"]'))
    assert not fc.facts_ok(FACTS, asker('["true", "true", "true"]'))


def test_unreadable_or_failing_judge_fails_open():
    assert fc.facts_ok(FACTS, asker("I cannot say"))
    assert fc.facts_ok(FACTS, asker('["true"]'))

    def boom(prompt):
        raise RuntimeError("no providers")
    assert fc.facts_ok(FACTS, boom)


def test_switch_off(monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_FACT_CHECK", "off")
    assert fc.facts_ok(FACTS, asker('["false", "false", "false"]'))


TRIVIA = {"question": "Which planet has most moons?", "opt_a": "Saturn", "opt_b": "Mars", "opt_c": "Venus", "answer": "Saturn"}


def test_trivia_needs_the_answer_right_and_the_rest_wrong():
    assert fc.trivia_ok(TRIVIA, asker('["true", "false", "false"]'))
    assert not fc.trivia_ok(TRIVIA, asker('["true", "true", "false"]'))
    assert not fc.trivia_ok(TRIVIA, asker('["false", "false", "false"]'))


def test_generate_mixed_facts_rewrites_until_the_judge_agrees(monkeypatch):
    import engine.script_gen as sg
    replies = iter([json.dumps(FACTS), '["true", "false", "false"]', json.dumps(FACTS), '["true", "true", "false"]'])
    monkeypatch.setattr(sg, "get_llm_response", lambda *a, **k: next(replies))
    out = sg.generate_mixed_facts("science")
    assert sum(1 for f in out["facts"] if not f["truth"]) == 1


def test_generate_mixed_facts_gives_up_when_the_judge_never_agrees(monkeypatch):
    import engine.script_gen as sg
    monkeypatch.setattr(sg, "get_llm_response",
                        lambda p, *a, **k: '["false", "true", "false"]' if "fact checker" in p else json.dumps(FACTS))
    with pytest.raises(RuntimeError):
        sg.generate_mixed_facts("science")


def test_a_reply_that_is_not_a_verdict_list_is_unreadable():
    assert fc._verdicts('[{"fact": "x", "truth": true}, {"fact": "y"}, {"fact": "z"}]', 3) is None
    assert fc._verdicts('[{"verdict": "True"}, {"verdict": "false"}]', 2) == ["true", "false"]
