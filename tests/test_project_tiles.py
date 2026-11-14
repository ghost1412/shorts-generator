import json

from shortsflow import review


def _run(root, name, clips, with_thumb=True):
    folder = root / "sessions" / name
    folder.mkdir(parents=True)
    rows = []
    for i, title in enumerate(clips, start=1):
        video = folder / f"video_clip_{i}.mp4"
        video.write_bytes(b"x")
        if with_thumb:
            (folder / f"video_clip_{i}.jpg").write_bytes(b"x")
        rows.append({"clip_index": i, "video_path": str(video), "title": title, "thumbnail": f"video_clip_{i}.jpg"})
    (folder / "results.json").write_text(json.dumps({"clips": rows}), encoding="utf-8")
    return folder


def test_tiles_use_the_first_clip_and_skip_empty_runs(tmp_path):
    _run(tmp_path, "web_20261101_100000", ["First title", "Second"])
    (tmp_path / "sessions" / "empty").mkdir()
    (tmp_path / "sessions" / "empty" / "results.json").write_text(json.dumps({"clips": []}), encoding="utf-8")
    tiles = review.project_tiles(str(tmp_path))
    assert len(tiles) == 1
    assert tiles[0]["caption"].startswith("First title") and "2 shorts" in tiles[0]["caption"]
    assert tiles[0]["thumb"].endswith("video_clip_1.jpg") and tiles[0]["results"].endswith("results.json")


def test_tiles_respect_the_limit_and_newest_first(tmp_path):
    import os
    import time
    for i in range(4):
        folder = _run(tmp_path, f"web_2026110{i + 1}_100000", [f"T{i}"])
        os.utime(folder / "results.json", (time.time() + i, time.time() + i))
    tiles = review.project_tiles(str(tmp_path), limit=2)
    assert [t["caption"].split("\n")[0] for t in tiles] == ["T3", "T2"]


def test_no_sessions_folder_gives_no_tiles(tmp_path):
    assert review.project_tiles(str(tmp_path)) == []
