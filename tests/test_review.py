import json
import os
import zipfile

from shortsflow import review


def _run(tmp_path, clips):
    session = tmp_path / "sessions" / "run1"
    session.mkdir(parents=True)
    for c in clips:
        if c.get("make"):
            (session / c["video_path"]).write_bytes(b"video" + c["video_path"].encode())
            if c.get("thumbnail"):
                (session / c["thumbnail"]).write_bytes(b"jpg")
    rows = [{k: v for k, v in c.items() if k != "make"} for c in clips]
    (session / "results.json").write_text(json.dumps({"clips": rows}), encoding="utf-8")
    return str(session / "results.json")


def test_score_labels_are_plain_language():
    assert [review.score_label(s) for s in (95, 80, 79, 60, 59, 40, 39, 0)] == [
        "strong", "strong", "good", "good", "okay", "okay", "weak", "weak"]
    assert review.score_label(None) == "unrated" and review.score_label("x") == "unrated"


def test_load_results_resolves_paths_and_skips_missing_videos(tmp_path):
    path = _run(tmp_path, [
        {"make": True, "clip_index": 1, "video_path": "video_clip_1.mp4", "viral_score": 85, "title": "Great moment",
         "description": "Why it works", "tags": ["a b", "#c"], "thumbnail": "video_clip_1.jpg", "start": 1.5, "end": 20, "duration": 18.5},
        {"make": False, "clip_index": 2, "video_path": "gone.mp4", "title": "Missing file"},
        {"make": True, "video_path": "video_clip_3.mp4"},
    ])
    cards = review.load_results(path)
    assert [c["index"] for c in cards] == [1, 3]
    first = cards[0]
    assert os.path.isabs(first["video"]) and os.path.exists(first["video"]) and first["thumbnail"].endswith("video_clip_1.jpg")
    assert first["label"] == "strong" and first["title"] == "Great moment"
    assert cards[1]["title"] == "Clip 3" and cards[1]["thumbnail"] is None and cards[1]["label"] == "unrated"


def test_load_results_tolerates_bad_files(tmp_path):
    assert review.load_results(str(tmp_path / "nope.json")) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert review.load_results(str(bad)) == []


def test_card_text_has_title_description_and_hashtags():
    text = review.card_text({"title": "T", "description": "D", "tags": ["growth hacks", "#viral"]})
    assert text == "T\n\nD\n\n#growthhacks #viral"
    assert review.card_text({"title": "Only"}) == "Only"


def test_build_zip_bundles_videos_thumbnails_and_text(tmp_path):
    path = _run(tmp_path, [
        {"make": True, "clip_index": 1, "video_path": "video_clip_1.mp4", "title": "One: the start!", "thumbnail": "video_clip_1.jpg",
         "description": "d1", "tags": ["x"]},
        {"make": True, "clip_index": 2, "video_path": "video_clip_2.mp4", "title": "Two"},
    ])
    cards = review.load_results(path)
    out = review.build_zip(cards, str(tmp_path / "out" / "shorts.zip"))
    names = sorted(zipfile.ZipFile(out).namelist())
    assert names == ["01_One_the_start.jpg", "01_One_the_start.mp4", "01_One_the_start.txt", "02_Two.mp4", "02_Two.txt"]
    assert zipfile.ZipFile(out).read("01_One_the_start.txt").decode() == "One: the start!\n\nd1\n\n#x"
    assert review.build_zip([], str(tmp_path / "empty.zip")) is None


def test_recent_runs_lists_newest_first_with_readable_labels(tmp_path):
    for name, mtime, clips in (("web_20261101_083000", 1000, 1), ("web_20261103_120000", 2000, 2)):
        d = tmp_path / "sessions" / name
        d.mkdir(parents=True)
        f = d / "results.json"
        f.write_text(json.dumps({"clips": [{}] * clips}))
        os.utime(f, (mtime, mtime))
    (tmp_path / "sessions" / "no_results").mkdir()
    labels = [n for n, _ in review.recent_runs(str(tmp_path))]
    assert labels == ["3 Nov 2026, 12:00 - 2 shorts", "1 Nov 2026, 08:30 - 1 short"]
    assert review.recent_runs(str(tmp_path / "missing")) == []
    assert review.run_label("custom_name", str(tmp_path / "nope.json")) == "custom_name"
