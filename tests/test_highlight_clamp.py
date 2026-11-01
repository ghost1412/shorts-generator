from engine.analysis import clamp_highlights


def H(s, e, **kw):
    return dict(start=s, end=e, **kw)


def test_window_past_the_end_is_clamped():
    out = clamp_highlights([H(92.5, 110.0, score=5)], 100.0)
    assert out == [H(92.5, 100.0, score=5)]


def test_window_that_barely_fits_is_dropped():
    assert clamp_highlights([H(99.9, 115.0)], 100.0) == []


def test_inside_windows_and_unknown_duration_are_untouched():
    hs = [H(10.0, 40.0), H(50.0, 70.0)]
    assert clamp_highlights(hs, 100.0) == hs
    assert clamp_highlights(hs, None) is hs


def test_negative_start_is_clamped_and_input_not_mutated():
    src = [H(-2.0, 20.0)]
    assert clamp_highlights(src, 100.0) == [H(0.0, 20.0)]
    assert src == [H(-2.0, 20.0)]
