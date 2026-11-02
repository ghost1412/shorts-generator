from engine.analysis import _to_seconds, normalize_highlight


def test_to_seconds_accepts_numbers_strings_and_clock_times():
    assert _to_seconds(30) == 30.0
    assert _to_seconds("30.5") == 30.5
    assert _to_seconds("30s") == 30.0
    assert _to_seconds("01:30") == 90.0
    assert _to_seconds("1:02:03") == 3723.0
    for bad in (None, "", "abc", True, [1], "1:2:3:4"):
        assert _to_seconds(bad) is None


def test_clip_start_clip_end_from_a_local_model():
    # what qwen2.5:7b actually returned on a real run
    h = normalize_highlight({"clip_start": 150.48, "clip_end": 193.74, "hook_text": "Petey's inappropriate comments",
                             "tone": "fail", "viral_score": 85})
    assert (h["start"], h["end"]) == (150.48, 193.74)
    assert h["hook_text"] == "Petey's inappropriate comments" and h["viral_score"] == 85


def test_other_common_variants():
    assert normalize_highlight({"start_time": "00:10", "end_time": "00:40"})["end"] == 40.0
    assert normalize_highlight({"begin": 5, "stop": 20, "title": "T"})["hook_text"] == "T"
    assert normalize_highlight({"startTime": 1, "endTime": 2})["start"] == 1.0


def test_canonical_keys_win_and_clock_strings_are_converted():
    h = normalize_highlight({"start": "0:10", "end": 50, "clip_start": 999})
    assert (h["start"], h["end"]) == (10.0, 50)


def test_missing_times_stay_missing_and_input_is_not_mutated():
    src = {"clip_start": 5}
    out = normalize_highlight(src)
    assert "end" not in out and src == {"clip_start": 5}
