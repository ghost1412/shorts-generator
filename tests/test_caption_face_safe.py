"""Animated captions move off a close-up speaker's mouth only at the default height (engine.caption_layout.face_safe_y)."""
from engine.caption_layout import DEFAULT_Y, FACE_SAFE_Y, face_safe_y


def _track(cx, cy, size, n=12):
    return [(cx, cy, size)] * n


def test_default_with_big_low_face_moves_to_lower_third():
    # face centre at 55% height, 30% tall: chin at (0.55 + 0.15) * 1920 = 1344, under the default caption top
    assert face_safe_y(DEFAULT_Y, _track(0.5, 0.55, 0.30)) == FACE_SAFE_Y


def test_default_with_small_face_stays():
    assert face_safe_y(DEFAULT_Y, _track(0.5, 0.6, 0.08)) == DEFAULT_Y


def test_default_with_high_face_stays():
    # chin at (0.3 + 0.1) * 1920 = 768, well above the captions
    assert face_safe_y(DEFAULT_Y, _track(0.5, 0.3, 0.20)) == DEFAULT_Y


def test_explicit_height_is_never_changed():
    assert face_safe_y(900, _track(0.5, 0.55, 0.30)) == 900
    assert face_safe_y(1480, _track(0.5, 0.55, 0.30)) == 1480


def test_no_faces_keeps_height():
    assert face_safe_y(DEFAULT_Y, []) == DEFAULT_Y
    assert face_safe_y(DEFAULT_Y, [None] * 12) == DEFAULT_Y


def test_face_in_few_frames_keeps_height():
    track = [(0.5, 0.55, 0.30)] * 3 + [None] * 9
    assert face_safe_y(DEFAULT_Y, track) == DEFAULT_Y


def test_median_decides_with_mixed_frames():
    track = [(0.5, 0.55, 0.30)] * 8 + [(0.5, 0.3, 0.20)] * 4
    assert face_safe_y(DEFAULT_Y, track) == FACE_SAFE_Y
