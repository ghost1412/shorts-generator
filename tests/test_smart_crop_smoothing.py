from engine.video_gen import generate_ffmpeg_crop_filter, smooth_focal_points


def test_a_subject_that_moves_is_followed_within_a_few_seconds():
    # one point every 0.33 s (the detector's sampling): the subject jumps from the left to the right side at t=1
    raw = [(i * 0.33, 0.2 if i * 0.33 < 1 else 0.8) for i in range(40)]
    out = dict(smooth_focal_points(raw))
    t_follow = min(t for t, x in out.items() if t > 1 and x >= 0.7)
    assert t_follow - 1 < 3.0          # the old smoothing needed more than 10 s to get past 0.44


def test_speed_is_capped_and_noise_is_ignored():
    raw = [(0.0, 0.5), (0.1, 0.52), (0.2, 0.49), (0.3, 0.5), (0.4, 1.0)]
    out = smooth_focal_points(raw)
    xs = [x for _, x in out]
    assert all(abs(x - 0.5) < 1e-9 for x in xs[:4])             # inside the deadband: the camera does not twitch
    assert xs[4] - xs[3] <= 0.5 * 0.1 + 1e-9                    # at most 50% of the width per second


def test_crop_filter_still_builds():
    pts = {i * 0.5: 0.3 + 0.01 * i for i in range(10)}
    f = generate_ffmpeg_crop_filter(pts, 0.0, 5.0)
    assert f.startswith("crop=") and "iw" in f
