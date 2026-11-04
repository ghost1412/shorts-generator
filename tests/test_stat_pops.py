from engine import auto_edit
from engine.stat_pops import find_stats


def _w(text, start=2.0, step=0.4):
    out, t = [], start
    for w in text.split():
        out.append({"word": " " + w, "start": round(t, 2), "end": round(t + 0.3, 2)})
        t += step
    return out


def test_currency_percent_and_unit_numbers_are_found_and_formatted():
    words = _w("people waste $200 a month and 73 percent never notice then in 10 years it grows to 3 million", start=1.5, step=0.9)
    texts = [s["text"] for s in find_stats(words, 40.0, min_spacing=1.0)]
    assert "$200" in texts and "73%" in texts and "10 YEARS" in texts and "3 MILLION" in texts


def test_years_small_numbers_and_edges_are_skipped():
    assert find_stats(_w("back in 2019 we had 3 tips and 7 rules", start=2.0), 30.0) == []
    assert find_stats(_w("it was $50", start=0.1), 30.0) == []                       # in the first second
    assert find_stats(_w("it cost $50", start=28.9), 30.0) == []                     # in the last moment
    assert find_stats(_w("2 days later", start=3.0), 30.0) == []                     # small time units are not striking
    assert [s["text"] for s in find_stats(_w("2024 sales were 1,500 units", start=3.0), 30.0)] == ["1,500"]


def test_crowded_numbers_keep_the_biggest_and_stay_apart():
    words = _w("it cost $200 and then $900 and later $50000 and $300", start=2.0, step=0.5)
    out = find_stats(words, 40.0)
    assert [s["text"] for s in out] == ["$50000"]                                    # all within 4 s of each other: the biggest wins
    spaced = _w("one $200 two three four five six seven eight nine $900", start=2.0, step=0.6)
    assert len(find_stats(spaced, 40.0)) == 2


def test_shape_of_a_pop():
    out = find_stats(_w("it costs $200", start=5.0), 30.0)
    assert out == [{"start": 5.8, "end": 7.5, "text": "$200"}]
    assert find_stats([], 30.0) == [] and find_stats(_w("it costs $200", start=2.0), 3.0) == []       # too short a clip


def test_sfx_and_summary_follow_the_stat_pops():
    cfg = {"sfx": {"zoom": None, "broll": None, "cut": None, "stat": "pop"}}
    ev = auto_edit.build_sfx_events(cfg, [], [], {"duration": 3.0}, [{"start": 4.0, "end": 5.7, "text": "$200"}])
    assert [(e["t"], e["kind"]) for e in ev] == [(7.0, "pop")] and "$200" in ev[0]["why"]
    assert auto_edit.build_sfx_events({"sfx": {"stat": None}}, [], [], None, [{"start": 1, "end": 2, "text": "1"}]) == []
    assert "2 number pop-ups ($200, 73%)" in auto_edit.summarize({"stats": ["$200", "73%"]})


def test_presets_switch_stat_pops_on_for_talk_styles():
    import argparse
    for name, expected in (("podcast", True), ("hype", True), ("educational", True), ("vlog", False)):
        a = argparse.Namespace(tighten=False, remove_fillers=False, clean_audio=False, hook_overlay=False, auto_zoom=False, cold_open=False,
                               broll=False, caption_emoji=False, use_remotion=False, tighten_mode="cut", caption_style="HORMOZI",
                               video_filter="none", stat_pops=False)
        auto_edit.apply_preset(a, name, "medium", [])
        assert bool(a.stat_pops) is expected, name
