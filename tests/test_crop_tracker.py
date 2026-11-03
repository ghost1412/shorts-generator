"""CropTracker: the horizontal crop centre must ignore one-off false faces and not stick at a stale position."""
from engine.analysis import CropTracker

W = 960
DT = 0.33


def face(cx_fraction, size=100):
    return [(int(cx_fraction * W - size / 2), 100, size, size)]


def test_single_false_face_does_not_move_the_crop():
    t = CropTracker()
    t.update(face(0.95), W, DT)           # one false detection at the right edge
    t.update([], W, DT)
    assert t.x == 0.5


def test_a_real_face_is_followed_after_confirmation():
    t = CropTracker()
    t.update(face(0.3), W, DT)
    assert t.x == 0.5                      # first sighting only waits
    t.update(face(0.3), W, DT)
    assert abs(t.x - 0.3) < 0.01           # confirmed: jumps to the face


def test_follows_a_slow_pan_smoothly():
    t = CropTracker()
    for _ in range(2):
        t.update(face(0.4), W, DT)
    t.update(face(0.45), W, DT)
    assert 0.40 < t.x < 0.45


def test_cut_to_another_face_snaps_after_two_samples():
    t = CropTracker()
    for _ in range(3):
        t.update(face(0.2), W, DT)
    t.update(face(0.8), W, DT)
    assert t.x < 0.3                       # unconfirmed, still on the old face
    t.update(face(0.8), W, DT)
    assert abs(t.x - 0.8) < 0.01


def test_holds_then_eases_back_to_centre_without_faces():
    t = CropTracker(hold_seconds=2.0)
    for _ in range(3):
        t.update(face(0.9), W, DT)
    held = t.x
    for _ in range(5):                     # 1.65 s: still holding
        t.update([], W, DT)
    assert t.x == held
    for _ in range(60):                    # long faceless scene
        t.update([], W, DT)
    assert abs(t.x - 0.5) < 0.05


def test_reset_clears_position_between_segments():
    t = CropTracker()
    for _ in range(3):
        t.update(face(0.9), W, DT)
    t.reset()
    assert t.x == 0.5 and t.locked is None
