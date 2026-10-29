import json

from engine.utils import find_fact_start_times


def write_subs(tmp_path, words):
    path = tmp_path / "subs.json"
    path.write_text(json.dumps([{"word": w, "start": t, "end": t + 0.3} for w, t in words]))
    return str(path)


def test_finds_each_number_marker_in_order(tmp_path):
    subs = write_subs(tmp_path, [
        ("Two", 0.5), ("of", 0.8), ("these", 1.0), ("Number", 5.6), ("1.", 5.9), ("fact", 6.2),
        ("Number", 11.8), ("two.", 12.1), ("Number", 17.3), ("3.", 17.6),
        ("which", 25.0), ("number", 27.2), ("two", 27.5),  # "rewatch number two" must not match fact 2
    ])
    assert find_fact_start_times(subs, 3) == [5.6, 11.8, 17.3]


def test_returns_none_when_a_marker_is_missing(tmp_path):
    subs = write_subs(tmp_path, [("Number", 1.0), ("1", 1.2), ("Number", 4.0), ("2", 4.2)])
    assert find_fact_start_times(subs, 3) is None


def test_missing_file_returns_none(tmp_path):
    assert find_fact_start_times(str(tmp_path / "nope.json"), 3) is None
