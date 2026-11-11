from engine.transcript_edit import subtract_intervals, word_pause_cuts


def _tr(*words):
    return {"segments": [{"start": words[0][0], "end": words[-1][1],
                          "words": [{"word": "w", "start": s, "end": e} for s, e in words]}]}


def test_pauses_between_words_are_cut_with_a_margin():
    tr = _tr((0.0, 0.5), (0.6, 1.0), (2.5, 3.0), (10.0, 10.5))
    # 0.1 s: speech; 1.5 s: a pause -> cut 1.2..2.3; 7 s: longer than 4 s, left alone (music, action)
    assert word_pause_cuts(tr) == [(1.2, 2.3)]


def test_subtract_splits_keep_intervals_around_cuts():
    assert subtract_intervals([(0, 10)], [(2, 3), (5, 6)]) == [(0, 2), (3, 5), (6, 10)]
    assert subtract_intervals([(0, 4), (6, 10)], [(3, 7)]) == [(0, 3), (7, 10)]
    assert subtract_intervals([(0, 10)], []) == [(0, 10)]
    assert subtract_intervals([(1, 2)], [(0, 5)]) == []


def test_no_words_means_no_cuts():
    assert word_pause_cuts({"segments": []}) == []
    assert word_pause_cuts(None) == []


def test_protect_speech_adds_words_back_to_loudness_keeps():
    from engine.transcript_edit import protect_speech
    tr = _tr((1.0, 1.5), (5.0, 5.4))
    # loudness kept only 0-0.5 and 4.9-5.1: both words come back whole (with 0.1 s each side)
    assert protect_speech([(0.0, 0.5), (4.9, 5.1)], tr) == [(0.0, 0.5), (0.9, 1.6), (4.9, 5.5)]
    assert protect_speech([(0, 10)], tr) == [(0, 10)]
    assert protect_speech([], {"segments": []}) == []
