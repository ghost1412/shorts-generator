import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import gold_sheet  # noqa: E402


def test_times_and_moments_parse():
    assert gold_sheet.parse_time("90") == 90 and gold_sheet.parse_time("1:30") == 90 and gold_sheet.parse_time("1:02:10") == 3730
    text = "12:30-13:05  # the bit about water\n\n# a comment line\n1:02:10 to 1:02:50\n90-120\n"
    assert gold_sheet.parse_moments(text) == [[750.0, 785.0], [3730.0, 3770.0], [90.0, 120.0]]


def test_bad_lines_are_reported_with_their_number():
    with pytest.raises(ValueError, match="line 2"):
        gold_sheet.parse_moments("1:00-1:30\nnonsense\n")
    with pytest.raises(ValueError, match="end must be after"):
        gold_sheet.parse_moments("2:00-1:00\n")


def test_sheet_has_a_heading_per_block_and_a_stamp_per_line():
    segs = [{"start": 5, "end": 9, "text": "First line."}, {"start": 70, "end": 75, "text": "Second line."}, {"start": 3700, "end": 3705, "text": "Late line."}]
    sheet = gold_sheet.build_sheet(segs, title="T", block=60)
    assert "## 0:05" in sheet and "## 1:10" in sheet and "## 1:01:40" in sheet
    assert "[0:05] First line." in sheet and "[1:01:40] Late line." in sheet


def test_cli_sheet_and_build_round_trip(tmp_path):
    session = tmp_path / "bench"
    session.mkdir()
    (session / "transcript.json").write_text(json.dumps({"segments": [{"start": 1, "end": 4, "text": "Hello there."}]}), encoding="utf-8")
    out = tmp_path / "sheet.md"
    assert gold_sheet.main(["sheet", str(session), "--out", str(out)]) == 0
    assert "[0:01] Hello there." in out.read_text(encoding="utf-8")
    moments = tmp_path / "m.txt"
    moments.write_text("0:10-0:40\n", encoding="utf-8")
    gold = tmp_path / "gold.json"
    assert gold_sheet.main(["build", str(moments), "--video", "video.webm", "--out", str(gold)]) == 0
    assert json.loads(gold.read_text(encoding="utf-8")) == {"video.webm": [[10.0, 40.0]]}
