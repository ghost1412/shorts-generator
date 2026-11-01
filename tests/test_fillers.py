from engine import fillers


def seg(*words):
    return {"words": [{"word": w, "start": s, "end": e} for w, s, e in words]}


def test_is_filler_handles_punctuation_and_case():
    assert fillers.is_filler(" Um,") and fillers.is_filler("UH.") and fillers.is_filler("hmm")
    assert not fillers.is_filler("umbrella") and not fillers.is_filler("") and not fillers.is_filler(None)


def test_find_filler_spans_pads_and_merges():
    segments = [seg(("So", 0, 0.4), (" um,", 0.5, 0.8), (" uh", 0.82, 1.0), ("prices", 1.2, 1.6), ("er", 5.0, 5.2))]
    spans = fillers.find_filler_spans(segments, pad_start=0.05, pad_end=0.05)
    assert spans == [(0.45, 1.05), (4.95, 5.25)]  # um+uh merged into one cut


def test_carve_splits_intervals_and_drops_slivers():
    assert fillers.carve([(0, 10)], [(2, 3), (7, 7.05)]) == [(0, 2), (3, 7), (7.05, 10)]
    assert fillers.carve([(0, 10)], [(0, 9.95)]) == []          # remainder shorter than min_keep
    assert fillers.carve([(0, 4), (6, 10)], [(3, 7)]) == [(0, 3), (7, 10)]
    assert fillers.carve([(0, 5)], [(8, 9)]) == [(0, 5)]


def test_remove_fillers_uses_whole_video_when_no_silence_intervals():
    segments = [seg(("hi", 0, 0.5), ("um", 2.0, 2.3), ("there", 2.5, 3.0))]
    keep, n = fillers.remove_fillers([], segments, 6.0)
    assert n == 1 and keep[0][0] == 0.0 and keep[-1][1] == 6.0
    assert not any(a < 2.15 < b for a, b in keep)
    assert fillers.remove_fillers([(0, 6.0)], [seg(("hi", 0, 1))], 6.0) == ([(0, 6.0)], 0)


def _envelope(fps, length, bursts):
    import numpy as np
    env = np.zeros(int(length * fps))
    for a, b, level in bursts:
        env[int(a * fps):int(b * fps)] = level
    return env


def test_refine_spans_snaps_to_the_real_sound():
    # Whisper says the "uh" is at 8.94-9.04 but the sound is 8.75-9.0; neighbours are 0.5 s away
    env = _envelope(100, 12, [(8.75, 9.0, 0.15), (9.5, 10.2, 0.4), (7.9, 8.5, 0.3)])
    (s, e), = fillers.refine_spans([(8.91, 9.14)], env, 100)
    assert s <= 8.77 and e >= 9.0
    assert s > 8.5 and e < 9.4                      # does not run into the neighbouring words


def test_refine_spans_stops_at_a_valley_between_words():
    env = _envelope(100, 6, [(1.0, 1.4, 0.3), (1.5, 1.8, 0.2), (1.8, 2.5, 0.4)])
    (s, e), = fillers.refine_spans([(1.5, 1.8)], env, 100)
    assert s >= 1.45 and e <= 1.85  # the louder word right after it is left alone


def test_refine_spans_without_audio_energy_keeps_original():
    assert fillers.refine_spans([(1.0, 1.3)], [0.0] * 500, 100) == [(1.0, 1.3)]
