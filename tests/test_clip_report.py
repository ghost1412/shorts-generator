import csv
import os

import pytest

from engine import clip_report as cr


def _data(tmp_path):
    clip1 = str(tmp_path / "clip_1.mp4")
    clip2 = str(tmp_path / "clip_2.mp4")
    highlights = [
        {"start": 63.4, "end": 95.0, "viral_score": 86, "hook_text": "Never do this"},
        {"start": 3725, "end": 3750.5, "viral_score": 35, "hook_text": "Pipe | char\nnewline"},
        {"start": 10, "end": 20},                                   # no score, no file yet
    ]
    meta = [{"title": "Title one", "thumbnail": "clip_1.jpg"}, {"title": "Ünïcode 标题"}]
    return highlights, [clip1, clip2], meta


def test_clock_formats_minutes_and_hours():
    assert cr.clock(63.4) == "1:03" and cr.clock(3725) == "1:02:05" and cr.clock(0) == "0:00"
    assert cr.clock(None) == "" and cr.clock("x") == ""


def test_build_rows_has_label_relative_paths_and_fallbacks(tmp_path):
    highlights, files, meta = _data(tmp_path)
    rows = cr.build_rows(highlights, files, meta, str(tmp_path))
    assert [r["clip"] for r in rows] == [1, 2, 3]
    r1, r2, r3 = rows
    assert (r1["title"], r1["start"], r1["end"], r1["duration_s"]) == ("Title one", "1:03", "1:35", 31.6)
    assert r1["label"] == "strong" and r1["score"] == 86 and r1["file"] == "clip_1.mp4" and r1["thumbnail"] == "clip_1.jpg"
    assert r2["label"] == "weak" and r2["thumbnail"] == ""
    assert r3["title"] == "Clip 3" and r3["label"] == "unrated" and r3["score"] == "" and r3["file"] == ""
    assert list(r1) == list(cr.COLUMNS)


def test_markdown_escapes_pipes_and_lists_every_clip(tmp_path):
    highlights, files, meta = _data(tmp_path)
    meta[1]["title"] = "A | B"
    md = cr.to_markdown(cr.build_rows(highlights, files, meta, str(tmp_path)), source="talk.mp4")
    assert md.startswith("# Clip report") and "Source: `talk.mp4`" in md and "3 clip(s)." in md
    assert "A \\| B" in md and "strong (86)" in md and "1:03-1:35 (31.6 s)" in md
    assert md.count("\n| ") == 5  # header + separator + 3 rows


@pytest.mark.parametrize("fmt,expected", [("md", ["clip_report.md"]), ("csv", ["clip_report.csv"]),
                                          ("both", ["clip_report.md", "clip_report.csv"])])
def test_write_report_formats(tmp_path, fmt, expected):
    highlights, files, meta = _data(tmp_path)
    rows = cr.build_rows(highlights, files, meta, str(tmp_path))
    paths = cr.write_report(rows, str(tmp_path), fmt, source="s")
    assert [os.path.basename(p) for p in paths] == expected and all(os.path.exists(p) for p in paths)


def test_csv_round_trips_unicode_and_has_the_columns(tmp_path):
    highlights, files, meta = _data(tmp_path)
    rows = cr.build_rows(highlights, files, meta, str(tmp_path))
    (path,) = cr.write_report(rows, str(tmp_path), "csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        back = list(csv.DictReader(f))
    assert list(back[0]) == list(cr.COLUMNS)
    assert back[1]["title"] == "Ünïcode 标题" and back[1]["hook"] == "Pipe | char\nnewline"
    assert back[0]["label"] == "strong"


def test_write_report_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError, match="--clip_report"):
        cr.write_report([], str(tmp_path), "pdf")


def test_flags_exist_on_the_pipeline_parser():
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "shortsflow", "_main.py"), encoding="utf-8").read()
    assert re.search(r'"--clip_report", nargs="\?", const="md"', src) and '"--zh_script"' in src
