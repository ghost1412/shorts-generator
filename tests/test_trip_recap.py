import json
import os
import shutil
import subprocess

import pytest

from engine import trip_recap as tr


def test_natural_order():
    assert sorted(["day10", "day2", "day1"], key=tr.natural_key) == ["day1", "day2", "day10"]


def test_group_days_by_name_and_folder(tmp_path):
    for name in ("Day2_b.mp4", "day1_a.mp4", "day 10.mp4", "day2_a.mp4"):
        (tmp_path / name).write_bytes(b"x")
    days = tr.group_days(tr.collect_videos([str(tmp_path)]))
    assert [[os.path.basename(p) for p in d] for d in days] == [["day1_a.mp4"], ["Day2_b.mp4", "day2_a.mp4"][::-1], ["day 10.mp4"]]


def test_group_days_subfolders(tmp_path):
    for d in ("Day 2", "Day 1"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "clip.mp4").write_bytes(b"x")
    days = tr.group_days(tr.collect_videos([str(tmp_path)]))
    assert [os.path.basename(os.path.dirname(d[0])) for d in days] == ["Day 1", "Day 2"]


def test_files_without_any_hint_become_one_day_each(tmp_path):
    for n in ("b.mp4", "a.mp4"):
        (tmp_path / n).write_bytes(b"x")
    days = tr.group_days([(str(tmp_path / "b.mp4"), None), (str(tmp_path / "a.mp4"), None)])
    assert [os.path.basename(d[0]) for d in days] == ["a.mp4", "b.mp4"]


def test_plan_counts_fills_the_length():
    n, clip = tr.plan_counts(3, 60)
    assert n >= 1 and 3 * (tr.CARD_SECONDS + n * clip) == pytest.approx(60, abs=6)
    assert tr.plan_counts(1, 10)[0] >= 1


def test_pick_windows_prefers_loud_parts_and_spreads():
    levels = [-60.0] * 100
    for i in range(70, 76):
        levels[i] = -10.0
    w = tr.pick_windows(100, 3, 5, levels)
    assert len(w) == 3 and w == sorted(w)
    assert any(abs(a - 70) < 3 for a, _ in w)               # the loud stretch is chosen
    assert all(e - s == pytest.approx(5, abs=0.01) for s, e in w)
    assert tr.pick_windows(3, 3, 5) == [[0.0, 3.0]]          # a very short video gives one window


def test_itinerary_parsing_and_fallback():
    days = [{"moments": [{"file": "a.mp4", "start": 1, "visual": "a lake"}, {"file": "a.mp4", "start": 9}]}]
    good = '{"title": "Almaty", "days": [{"title": "Lakes", "summary": "A day at the lake.", "captions": ["Big Almaty Lake"]}]}'
    it = tr.write_itinerary("Almaty", "", days, ask=lambda p: good)
    assert it["title"] == "Almaty" and it["days"][0]["captions"] == ["Big Almaty Lake", ""]
    bad = tr.write_itinerary("Almaty", "", days, ask=lambda p: "nonsense")
    assert bad["days"][0]["title"] == "Day 1"
    boom = tr.write_itinerary("", "", days, ask=lambda p: 1 / 0)
    assert boom["title"] == "Trip recap"
    assert "a lake" in tr.build_prompt("Almaty", "note", days)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")
def test_make_recap_end_to_end(tmp_path):
    def make(path, w, h, secs, tone):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=15:duration={secs}",
                        "-f", "lavfi", "-i", f"sine=f={tone}:d={secs}", "-shortest", "-pix_fmt", "yuv420p", str(path)], check=True)

    (tmp_path / "day1").mkdir()
    (tmp_path / "day2").mkdir()
    make(tmp_path / "day1" / "a.mp4", 640, 360, 20, 300)
    make(tmp_path / "day2" / "b.mp4", 360, 640, 20, 600)          # a portrait phone video too
    ask = lambda p: json.dumps({"title": "Test Trip", "days": [  # noqa: E731
        {"title": "Arrival", "summary": "We landed.", "captions": ["Hello", "Lake"]},
        {"title": "Mountains", "summary": "Up high.", "captions": ["Peak", "View"]}]})
    res = tr.make_recap([str(tmp_path / "day1"), str(tmp_path / "day2")], str(tmp_path / "out"), trip_name="Test", total_seconds=24, ask=ask)
    assert res["days"] == 2 and os.path.isfile(res["video"])
    dur, w, h = tr.video_info(res["video"])
    assert (w, h) == (1080, 1920) and 14 < dur < 36
    assert tr.has_audio(res["video"])
    md = open(res["itinerary_md"], encoding="utf-8").read()
    assert "Day 1: Arrival" in md and "Day 2: Mountains" in md


def test_no_videos_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError):
        tr.make_recap([str(tmp_path)], str(tmp_path / "o"))


def _jpeg(color, noise=False):
    import io
    from PIL import Image
    img = Image.new("RGB", (64, 64), color)
    if noise:
        for x in range(0, 64, 2):
            for y in range(64):
                img.putpixel((x, y), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def test_scenic_score_prefers_colourful_frames():
    assert tr.scenic_score(_jpeg((30, 144, 255), noise=True)) > tr.scenic_score(_jpeg((90, 90, 90)))
    assert tr.scenic_score(b"not an image") == 0.0


def test_pick_glimpses_spreads_over_days_and_follows_trip_order():
    days = [{"infos": [("d1.mp4", 60, 640, 360)]}, {"infos": [("d2.mp4", 60, 640, 360)]}, {"infos": [("d3.mp4", 60, 640, 360)]}]
    grab = lambda f, s, e: [f"{f}|{s}".encode()]  # noqa: E731
    # day 1 is the prettiest by far, but may not fill the whole opening
    score = lambda b: 1.0 if b.startswith(b"d1") else 0.2 + (hash(b) % 100) / 1000  # noqa: E731
    g = tr.pick_glimpses(days, 5, 1.4, grab=grab, score=score)
    assert len(g) == 5
    per_day = [sum(1 for x in g if x["day"] == d) for d in range(3)]
    assert max(per_day) <= 3 and min(per_day) >= 1
    assert [x["day"] for x in g] == sorted(x["day"] for x in g)


def test_hook_comes_from_ai_and_is_overridable():
    days = [{"moments": [{"file": "a.mp4", "start": 1}]}]
    good = '{"title": "Almaty", "hook": "Woke up at 4 AM just for this view", "days": [{"title": "Lakes", "summary": "", "captions": ["x"]}]}'
    assert tr.write_itinerary("Almaty", "woke up at 4am", days, ask=lambda p: good)["hook"] == "Woke up at 4 AM just for this view"
    assert "Use only facts from the traveller" in tr.build_prompt("Almaty", "note", days)


def test_parse_stops_and_split_into():
    assert tr.parse_stops("Kolsai Lake, Kaindy Lake; Charyn Canyon") == ["Kolsai Lake", "Kaindy Lake", "Charyn Canyon"]
    assert tr.parse_stops("") == [] and tr.parse_stops(None) == []
    g = tr.split_into([["a", "b", "c"], ["d", "e"]], 3)
    assert g == [["a", "b"], ["c", "d"], ["e"]]
    assert tr.split_into([["a"]], 3) == [["a"]]                       # never more stops than videos


def test_stop_names_are_used_verbatim_and_prompt_forbids_inventing():
    days = [{"moments": [{"file": "a.mp4", "start": 1}]}, {"moments": [{"file": "b.mp4", "start": 1}]}]
    stops = ["Kolsai Lake", "Kaindy Lake"]
    reply = '{"title": "Almaty tour", "hook": "h", "days": [{"title": "Whatever", "summary": "s", "captions": ["x"]}, {"title": "Else", "summary": "", "captions": [""]}]}'
    it = tr.write_itinerary("Almaty", "17 hour tour from 5 am", days, ask=lambda p: reply, stops=stops)
    assert [d["title"] for d in it["days"]] == stops
    p = tr.build_prompt("Almaty", "note", days, stops)
    assert "Never invent" in p and "Stop 1 = Kolsai Lake" in p
    assert tr.fallback_itinerary("", days, stops)["days"][1]["title"] == "Kaindy Lake"
    assert "## Stop 1: Kolsai Lake" in tr.itinerary_markdown(it, [{"moments": [{"file": "a.mp4", "start": 1}]}] * 2, "Stop")
