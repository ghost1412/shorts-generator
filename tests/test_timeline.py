from shortsflow import timeline


def test_source_length_uses_latest_end():
    assert timeline.source_length([{"end": 10}, {"end": 95.5}], [{"end": 60}]) == 95.5
    assert timeline.source_length([], []) == 0.0


def test_nudge_keeps_minimum_length_and_bounds():
    assert timeline.nudge(10, -1, 40, True) == 9.0
    assert timeline.nudge(39.5, 2, 40, True) == 39.0          # start cannot pass end - 1
    assert timeline.nudge(11, -5, 10, False) == 11.0          # end cannot go below start + 1
    assert timeline.nudge(0.5, -3, 20, True) == 0.0
    assert timeline.nudge(99, 5, 10, False, total=100) == 100.0
    assert timeline.nudge(None, 1, 5, True) is None


def test_timeline_html_draws_clip_cuts_and_others():
    out = timeline.timeline_html(10, 40, [(20, 22)], 100, others=[(50, 80)])
    assert out.count("sf-tl-clip") >= 2 and "sf-tl-cut" in out and "sf-tl-other" in out
    assert "left:10.00%;width:30.00%" in out
    assert "1:40" in out


def test_timeline_html_empty_for_bad_input():
    assert timeline.timeline_html(None, 5, [], 100) == ""
    assert timeline.timeline_html(5, 5, [], 100) == ""
    assert timeline.timeline_html(5, 9, [], 0) == ""


def test_nudge_view_moves_the_box_and_redraws_the_strip():
    s, e, html_out = timeline.nudge_view(12, 36, 1, True, 53, [], [(24, 48)])
    assert (s, e) == (13.0, 36)
    assert "0:13 to 0:36" in html_out
    s, e, html_out = timeline.nudge_view(12, 36, -1, False, 53)
    assert (s, e) == (12, 35.0) and "0:12 to 0:35" in html_out
