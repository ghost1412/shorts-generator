import json
import os

import pytest

from engine import gphotos_album as ga


def _item(i, ts, video=False, secs=10.0):
    meta = {"101428965": [0, "x"]}
    if video:
        meta[ga.VIDEO_KEY] = [int(secs * 1000), None, 1080, 1920]
    return [f"AF1Qip{i:04d}abcdefgh", [f"https://lh3.googleusercontent.com/pw/AP{i}", 1080, 1920, None], ts, "k", 1, 2, ["o"], [], 2, meta]


def _page(items, token="TOK"):
    data = [None, items, token, ["ALBUMID", "Eastland", []]]
    return ("<html>AF_initDataCallback({key: 'ds:1', hash: '2', data:" + json.dumps(data) + ", sideChannel: {}});</html>").encode()


def test_parse_page_and_rows():
    items = [_item(1, 1_000_000), _item(2, 2_000_000, video=True, secs=12)]
    album_id, title, got, token = ga.parse_page(_page(items).decode())
    assert (album_id, title, token) == ("ALBUMID", "Eastland", "TOK") and len(got) == 2
    rows = ga.to_rows(got)
    assert [r["video"] for r in rows] == [False, True] and rows[1]["seconds"] == 12.0


def test_unknown_page_is_a_clear_error():
    with pytest.raises(ga.AlbumError):
        ga.parse_page("<html>sign in</html>")


def test_pick_videos_skips_very_long_ones_and_orders_by_time():
    rows = ga.to_rows([_item(1, 3000, True, 20), _item(2, 1000, True, 1182), _item(3, 2000, True, 5), _item(4, 500, False)])
    kept, skipped = ga.pick_videos(rows, 300)
    assert [r["ts"] for r in kept] == [2000, 3000] and [r["seconds"] for r in skipped] == [1182.0]


def test_plan_files_one_folder_per_day_in_filming_order(tmp_path):
    day = 86_400_000
    base = 1_792_000_000_000
    rows = ga.to_rows([_item(1, base + 3_600_000, True), _item(2, base, True), _item(3, base + day + 1000, True)])
    plan = ga.plan_files(sorted(rows, key=lambda r: r["ts"]), str(tmp_path))
    folders = [os.path.basename(os.path.dirname(p)) for _, p in plan]
    assert folders[0].startswith("day1_") and folders[2].startswith("day2_") and folders[0] == folders[1]
    names = [os.path.basename(p) for _, p in plan[:2]]
    assert names == sorted(names)


def test_download_skips_existing_and_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(ga.time, "sleep", lambda s: None)
    row = {"url": "https://x/y"}
    path = str(tmp_path / "d" / "a.mp4")
    calls = []

    def fetch(url, timeout=0):
        calls.append(url)
        if len(calls) == 1:
            raise OSError("boom")
        return b"v" * 20000, url

    assert ga.download(row, path, fetch=fetch) and os.path.getsize(path) == 20000
    assert calls[0].endswith("=dv") and len(calls) == 2
    assert ga.download(row, path, fetch=fetch) and len(calls) == 2           # already there: no new request


def test_list_album_follows_continuation_pages(monkeypatch):
    first = _page([_item(1, 1000, True)], token="T1")
    monkeypatch.setattr(ga, "next_page", lambda aid, tok, key: ([_item(2, 2000, True)], None) if tok == "T1" else ([], None))
    title, rows = ga.list_album("https://photos.app.goo.gl/abc", fetch=lambda url, *a, **k: (first, "https://photos.google.com/share/X?key=K1"))
    assert title == "Eastland" and len(rows) == 2


def test_is_album_link():
    assert ga.is_album_link("https://photos.app.goo.gl/E5Hz9gXPSRHchNUv5")
    assert not ga.is_album_link("C:/videos/trip") and not ga.is_album_link("https://example.com/x")
