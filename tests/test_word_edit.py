import json

import pytest
from test_rerender import _fake_engine, _session

from engine import rerender
from shortsflow import word_edit

WORDS = [
    {"word": "Hello", "start": 5.0, "end": 5.4},
    {"word": "um", "start": 5.5, "end": 5.8},
    {"word": "so", "start": 5.9, "end": 6.1},
    {"word": "basically", "start": 6.1, "end": 6.7},
    {"word": "we", "start": 8.0, "end": 8.2},
    {"word": "win", "start": 8.3, "end": 8.8},
]


def _write_transcript(session):
    seg = {"words": [dict(w, word=" " + w["word"]) for w in WORDS]}
    (session / "transcript.json").write_text(json.dumps({"segments": [seg]}))


def test_load_words_reads_the_run_transcript_and_survives_missing_files(tmp_path):
    assert word_edit.load_words(str(tmp_path)) == []
    (tmp_path / "transcript.json").write_text("not json")
    assert word_edit.load_words(str(tmp_path)) == []
    _write_transcript(tmp_path)
    assert [w["word"] for w in word_edit.load_words(str(tmp_path))] == [w["word"] for w in WORDS]


def test_choices_cover_the_window_and_mark_existing_cuts():
    choices, ticked = word_edit.choices_for(WORDS, 5.0, 6.5, cuts=[(5.48, 5.86)])
    assert [c[0] for c in choices] == ["Hello", "um", "so", "basically"] and ticked == [1]
    assert word_edit.choices_for(WORDS, None, None) == ([], [])
    assert [i for _, i in word_edit.choices_for(WORDS, 8.0, 9.0)[0]] == [4, 5]       # values are positions in the whole transcript


def test_neighbouring_ticks_become_one_padded_cut_and_junk_is_ignored():
    spans = word_edit.spans_from_ticks(WORDS, [2, 3, 99, "1"])
    assert len(spans) == 1 and spans[0][0] == pytest.approx(5.5 - 0.02) and spans[0][1] == pytest.approx(6.7 + 0.06)
    assert len(word_edit.spans_from_ticks(WORDS, [0, 4])) == 2
    assert word_edit.spans_from_ticks(WORDS, []) == []


def test_span_argument_round_trips_and_rejects_garbage():
    spans = [(1.2, 1.8), (3.0, 3.5)]
    assert word_edit.parse_spans_arg(word_edit.spans_arg(spans)) == spans
    assert word_edit.parse_spans_arg("") == []
    with pytest.raises(ValueError, match="Cuts must look like"):
        word_edit.parse_spans_arg("abc")
    assert "2 cuts" in word_edit.summary(spans) and word_edit.summary([]) == "Nothing is cut."


def test_rerender_with_cuts_carves_the_keep_intervals_and_remembers_them(tmp_path, monkeypatch):
    session = _session(tmp_path)
    calls = {}
    _fake_engine(monkeypatch, calls)
    monkeypatch.chdir(tmp_path)

    clip = rerender.rerender_clip(str(session), 1, cuts=[(7.0, 8.0)])
    assert calls["kw"]["silence_intervals"] == [(0, 4), (5, 7.0), (8.0, 12)]
    assert calls["kw"]["remove_fillers"] is True and calls["kw"]["tighten_mode"] == "cut"
    assert clip["cuts"] == [[7.0, 8.0]]

    rerender.rerender_clip(str(session), 1, caption_style="GLOW_BOX")        # None keeps the cuts
    assert calls["kw"]["silence_intervals"] == [(0, 4), (5, 7.0), (8.0, 12)]
    rerender.rerender_clip(str(session), 1, cuts=[])                          # [] brings the words back
    assert calls["kw"]["silence_intervals"] == [(0, 4), (5, 12)] and "remove_fillers" not in calls["kw"]
    assert "cuts" not in json.loads((session / "results.json").read_text())["clips"][0]


def test_undo_brings_the_cuts_back_with_the_video(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _fake_engine(monkeypatch, {})
    monkeypatch.chdir(tmp_path)
    rerender.rerender_clip(str(session), 1, cuts=[(7.0, 8.0)])
    assert rerender.undo_rerender(str(session), 1) is True
    assert "cuts" not in json.loads((session / "results.json").read_text())["clips"][0]


def test_cutting_nearly_everything_is_refused_in_plain_words(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _fake_engine(monkeypatch, {})
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="less than 3 seconds"):
        rerender.rerender_clip(str(session), 1, cuts=[(5.2, 12.0)])
    assert (session / "video_clip_1.mp4").read_bytes() == b"old video"


def test_the_command_line_takes_cuts(tmp_path, monkeypatch, capsys):
    session = _session(tmp_path)
    calls = {}
    _fake_engine(monkeypatch, calls)
    monkeypatch.chdir(tmp_path)
    assert rerender.main([str(session), "1", "--cuts", "7:8"]) == 0
    assert calls["kw"]["silence_intervals"] == [(0, 4), (5, 7.0), (8.0, 12)]
    assert rerender.main([str(session), "1", "--cuts", "x"]) == 1
    assert "Cuts must look like" in capsys.readouterr().out


def test_browser_app_passes_the_ticked_words_as_cuts(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    import webui
    seg = {"words": [dict(w, word=" " + w["word"]) for w in WORDS]}
    (tmp_path / "transcript.json").write_text(json.dumps({"segments": [seg]}))
    card = {"index": 1, "session_dir": str(tmp_path), "start": 5.0, "end": 9.0, "cuts": []}
    choices, ticked, hint = webui.word_choices(card)
    assert len(choices) == 6 and ticked == [] and hint == "Nothing is cut."

    seen = {}

    def fake_rerender(cards, index, style, start, end, cuts=None):
        seen["cuts"] = cuts
        yield cards, "ok"
    monkeypatch.setattr(webui, "rerender_card", fake_rerender)
    list(webui.cut_words_handler(1)([card], [1], None, 5.0, 9.0))
    assert len(seen["cuts"]) == 1 and seen["cuts"][0][0] < 5.5 < seen["cuts"][0][1]
    with pytest.raises(Exception):
        list(webui.cut_words_handler(7)([card], [1], None, 5.0, 9.0))
