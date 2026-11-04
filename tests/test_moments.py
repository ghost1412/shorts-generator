import pytest

from engine.highlight_quality import sentence_spans, snap_clip
from engine.moments import parse_moments, parse_time


def test_times_in_every_format():
    assert parse_time("7:00") == 420 and parse_time("1:01:40") == 3700 and parse_time("420") == 420 and parse_time("7:00.5") == 420.5
    for bad in ("", "abc", "7:99:99:1", "-5", "7:"):
        with pytest.raises(ValueError, match="not a time"):
            parse_time(bad)


def test_ranges_lines_commas_and_single_times():
    out = parse_moments("1:01:40-1:02:30\n7:00-7:45, 420 - 465; 10:00", default_length=30)
    assert [(m["start"], m["end"]) for m in out] == [(420, 465), (420, 465), (600, 630), (3700, 3750)]   # sorted, a lone time gets the default length
    assert all(m["user_moment"] and m["viral_score"] == 90 and m["reason"] == "Chosen by you" for m in out)
    assert parse_moments("", 30) == [] and parse_moments(None, 30) == [] and parse_moments("  \n ", 30) == []


def test_dashes_that_word_processors_produce():
    assert [(m["start"], m["end"]) for m in parse_moments("7:00–7:45")] == [(420, 465)]                  # en dash
    assert [(m["start"], m["end"]) for m in parse_moments("7:00 — 7:45")] == [(420, 465)]                # em dash with spaces


def test_plain_language_errors():
    with pytest.raises(ValueError, match="end must come after the start"):
        parse_moments("7:45-7:00")
    with pytest.raises(ValueError, match="at least 3 seconds"):
        parse_moments("7:00-7:01")
    with pytest.raises(ValueError, match="only 10 minutes long"):
        parse_moments("12:00-12:30", video_seconds=600)
    with pytest.raises(ValueError, match="not a time"):
        parse_moments("seven o'clock")


def test_a_short_is_never_longer_than_a_minute_and_stays_in_the_video():
    assert parse_moments("0:00-5:00")[0]["end"] == 59.9
    assert parse_moments("9:50-10:30", video_seconds=600)[0]["end"] == 600


def test_snapping_leaves_the_users_exact_times_alone():
    words = [{"word": " word", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(60)]
    words[10]["word"] = " end."
    spans = sentence_spans({"segments": [{"words": words}]})
    own = {"start": 3.3, "end": 12.7, "user_moment": True}
    assert snap_clip(own, spans) is own                                                                # untouched
    ai = {"start": 3.3, "end": 12.7}
    assert snap_clip(ai, spans, min_len=3.0) != ai                                                     # an AI pick would have been moved
