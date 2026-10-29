from engine.media_gen import pick_video_file


def f(w, name=None):
    return {"width": w, "link": name or f"{w}.mp4"}


def test_prefers_exact_1080():
    assert pick_video_file([f(360), f(2160), f(1080), f(720)]) == "1080.mp4"


def test_otherwise_sharpest_up_to_1440():
    assert pick_video_file([f(360), f(720), f(1366), f(3840)]) == "1366.mp4"


def test_otherwise_smallest_above_1440():
    assert pick_video_file([f(3840), f(2160)]) == "2160.mp4"


def test_empty_list():
    assert pick_video_file([]) is None
