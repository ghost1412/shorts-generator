from engine import trip_recap as tr


def test_parse_lines_splits_on_bars_and_newlines_and_keeps_gaps():
    assert tr.parse_lines("Fry the nuts | Roast the khoya") == ["Fry the nuts", "Roast the khoya"]
    assert tr.parse_lines("one\ntwo") == ["one", "two"]
    assert tr.parse_lines("one |  | three") == ["one", "", "three"]       # a part can have no line
    assert tr.parse_lines("one | two |") == ["one", "two"]                # trailing empties dropped
    assert tr.parse_lines("") == [] and tr.parse_lines(None) == []
    assert tr.parse_lines(["a  b", "c"]) == ["a b", "c"]


def _g(day, name):
    return {"file": name, "start": 0.0, "end": 2.0, "size": (1080, 1920), "day": day}


def test_open_with_result_puts_the_last_part_first():
    glimpses = [_g(0, "a"), _g(1, "b"), _g(2, "c"), _g(2, "d")]
    days = [{"moments": []}, {"moments": []}, {"moments": []}]
    out = tr.payoff_first(glimpses, days)
    assert [g["file"] for g in out[:2]] == ["c", "d"] and [g["file"] for g in out] == ["c", "d", "a", "b"]


def test_open_with_result_adds_a_shot_when_the_last_part_had_none():
    glimpses = [_g(0, "a"), _g(1, "b")]
    days = [{"moments": []}, {"moments": []}, {"moments": [{"file": "fin", "start": 1.0, "end": 5.0, "size": (1080, 1920)}]}]
    out = tr.payoff_first(glimpses, days)
    assert out[0]["file"] == "fin" and out[0]["day"] == 2 and len(out) == len(glimpses)
    assert tr.payoff_first([], days) == [] and tr.payoff_first(glimpses, []) == glimpses


def test_cli_has_recap_lines_and_open_result():
    import os
    src = open(os.path.join(os.path.dirname(__file__), "..", "shortsflow", "_main.py"), encoding="utf-8").read()
    assert '"--recap_lines"' in src and '"--recap_open_result"' in src


def test_dissolve_graph_overlaps_every_join_and_fades_the_ends():
    graph, v, a = tr.dissolve_graph([4.0, 5.0, 3.0], d=0.5)
    assert (v, a) == ("[vout]", "[aout]")
    # join 1 starts 0.5 s before shot 1 ends (4.0 - 0.5); join 2 at 4 + 5 - 2 * 0.5 = 8.0 (the output so far is 8.5 s long)
    assert "[0:v][1:v]xfade=transition=fade:duration=0.500:offset=3.500[v1]" in graph
    assert "[v1][2:v]xfade=transition=fade:duration=0.500:offset=8.000[v2]" in graph
    assert "[0:a][1:a]acrossfade=d=0.500" in graph and "[a1][2:a]acrossfade=d=0.500" in graph
    total = 12.0 - 2 * 0.5
    assert f"fade=t=out:st={total - 1.0:.2f}:d=1.00[vout]" in graph and "afade=t=in:st=0:d=0.50" in graph


def test_dissolve_is_never_longer_than_the_shots_and_needs_two_shots():
    graph, _v, _a = tr.dissolve_graph([1.0, 1.0], d=0.6)
    assert "duration=0.450" in graph                 # capped at 45% of the shortest shot
    import pytest
    with pytest.raises(ValueError):
        tr.dissolve_graph([3.0])


def test_dissolve_is_a_known_transition_with_plain_per_shot_cuts():
    from engine import transitions
    assert "dissolve" in transitions.NAMES and transitions.validate("dissolve") == "dissolve"
    assert transitions.cut_types("dissolve", 3) == [None, None, None]
    assert transitions.resolve("dissolve", "hype") == "dissolve"           # an explicit choice always wins
    assert transitions.resolve("auto", "vlog") == "punch"                  # auto never dissolves
