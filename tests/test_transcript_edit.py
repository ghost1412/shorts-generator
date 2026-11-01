from engine.fillers import carve
from engine.transcript_edit import (
    clip_transcript, keep_intervals, plan_keeps, remap_transcript, render_edited_video, tighten_segment,
    PAD_END, PAD_START, cut_spans, export_text, flatten_words, norm, spans_from_edit, spans_from_phrases,
)

SEGMENTS = [{"words": [
    {"word": " So", "start": 0.0, "end": 0.3},
    {"word": " basically,", "start": 0.4, "end": 0.9},
    {"word": " you", "start": 1.0, "end": 1.2},
    {"word": " know,", "start": 1.2, "end": 1.5},
    {"word": " cats", "start": 1.6, "end": 2.0},
    {"word": " are", "start": 2.1, "end": 2.3},
    {"word": " you", "start": 2.4, "end": 2.6},
    {"word": " know", "start": 2.6, "end": 2.9},
    {"word": " great.", "start": 3.0, "end": 3.5},
]}]
WORDS = flatten_words(SEGMENTS)


def test_norm_and_flatten():
    assert norm(" Hello, ") == "hello"
    assert [w["word"] for w in WORDS][:2] == ["So", "basically,"]
    assert flatten_words([{"words": [{"word": " ...", "start": 0, "end": 1}]}]) == []


def test_phrase_cuts_every_occurrence():
    spans = spans_from_phrases(WORDS, ["You know"])
    assert spans == [(1.0 - PAD_START, 1.5 + PAD_END), (2.4 - PAD_START, 2.9 + PAD_END)]


def test_phrase_ignores_punctuation_and_case_and_missing():
    assert spans_from_phrases(WORDS, ["SO BASICALLY"]) == [(0.0, 0.9 + PAD_END)]
    assert spans_from_phrases(WORDS, ["dogs", ""]) == []


def test_edit_deleted_words_are_cut():
    edited = "So basically, cats are great."  # both "you know" pairs removed
    spans = spans_from_edit(WORDS, edited)
    assert spans == [(1.0 - PAD_START, 1.5 + PAD_END), (2.4 - PAD_START, 2.9 + PAD_END)]


def test_edit_replacements_and_inserts_cut_nothing():
    edited = "So basically, you know, kittens are you know great. Extra words here."
    assert spans_from_edit(WORDS, edited) == []


def test_unchanged_transcript_cuts_nothing():
    assert spans_from_edit(WORDS, export_text(WORDS)) == []


def test_export_roundtrip_with_deleted_line():
    lines = export_text(WORDS, sentence_gap=0.05).splitlines()
    assert len(lines) > 1
    spans = spans_from_edit(WORDS, "\n".join(lines[1:]))
    assert spans and spans[0][0] == 0.0  # first line removed -> cut starts at the very beginning


def test_cut_spans_merges_phrase_and_edit():
    spans = cut_spans(WORDS, phrases=["you know"], edited_text="So basically, you know, cats are you know")
    # edit deletes "great." (3.0-3.5); phrase deletes both "you know"
    assert len(spans) == 3
    assert spans[-1][0] == 3.0 - PAD_START


def test_spans_carve_out_of_keep_intervals():
    spans = spans_from_phrases(WORDS, ["cats are"])
    kept = carve([(0.0, 4.0)], spans)
    assert kept[0][1] == 1.6 - PAD_START and kept[1][0] == 2.3 + PAD_END


def test_keep_intervals_is_the_complement():
    assert keep_intervals([(1.0, 2.0), (3.0, 3.5)], total=5.0) == [(0.0, 1.0), (2.0, 3.0), (3.5, 5.0)]
    assert keep_intervals([(0.0, 2.0)], total=5.0) == [(2.0, 5.0)]
    assert keep_intervals([(1.0, 2.0)])[-1][0] == 2.0  # open-ended


def test_remap_drops_cut_words_and_shifts_the_rest():
    data = {"text": "x", "source_video_path": "/a.mp4", "segments": [dict(SEGMENTS[0], tokens=[1], text="x")]}
    spans = spans_from_phrases(WORDS, ["you know"])  # cuts 0.98-1.56 and 2.38-2.96
    out = remap_transcript(data, spans)
    words = [w["word"] for s in out["segments"] for w in s["words"]]
    assert [w.strip() for w in words] == ["So", "basically,", "cats", "are", "great."]
    cats = out["segments"][0]["words"][2]
    assert abs(cats["start"] - (1.6 - 0.58)) < 0.01  # shifted left by the removed "you know"
    assert out["segments"][0]["start"] == 0.0 and "tokens" not in out["segments"][0]
    assert data["segments"][0]["words"][2]["word"] == " you"  # input untouched


def test_remap_keeps_timeline_monotonic():
    spans = spans_from_phrases(WORDS, ["basically you know", "great"])
    out = remap_transcript({"segments": SEGMENTS}, spans)
    times = [t for s in out["segments"] for w in s["words"] for t in (w["start"], w["end"])]
    assert times == sorted(times)


def test_render_edited_video_cuts_audio_and_video(tmp_path):
    import shutil
    import subprocess
    import pytest
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg not installed")
    src = tmp_path / "src.mp4"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest", str(src)],
                   check=True, capture_output=True)
    out = tmp_path / "out.mp4"
    render_edited_video(str(src), keep_intervals([(1.0, 3.0)], total=6.0), str(out), str(tmp_path))
    err = subprocess.run([ff, "-i", str(out)], capture_output=True, text=True).stderr
    import re
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    assert abs(int(h) * 3600 + int(m) * 60 + float(s) - 4.0) < 0.3
    probe = subprocess.run([ff, "-i", str(out), "-map", "0:a", "-f", "null", "-"], capture_output=True, text=True).stderr
    h, m, s = re.findall(r"time=(\d+):(\d+):([\d.]+)", probe)[-1]
    assert abs(int(h) * 3600 + int(m) * 60 + float(s) - 4.0) < 0.3  # the audio track is cut too, not just the video


def test_plan_keeps_pads_merges_and_drops_slivers():
    keeps = plan_keeps([(1.0, 2.0), (2.2, 3.0), (5.0, 5.02), (7.0, 8.0)], 10.0, padding=0.1, min_gap=0.25)
    assert keeps == [(0.9, 3.1), (6.9, 8.1)]  # first two merge once padded, the 0.02 s sliver is dropped


def test_clip_transcript_is_clip_relative_and_retimed():
    data = {"segments": SEGMENTS}
    # clip = 0.9..3.6 of the source; keep 0-0.6 (basically/you) and 1.5-2.7 (cats are ... great) in clip time
    out = clip_transcript(data, 0.9, 3.6, [(0.0, 0.6), (1.5, 2.7)])
    words = [(w["word"].strip(), w["start"]) for s in out["segments"] for w in s["words"]]
    assert words[0][0] == "you" and words[0][1] == 0.1
    assert [w for w, _ in words] == ["you", "know,", "you", "know", "great."]  # cats/are sit in the cut gap 0.6-1.5
    assert words[2][1] == 0.6  # "you" (clip time 1.5) moves up by the 0.9 s gap
    assert all(t >= 0 for _, t in words)
    times = [t for s in out["segments"] for w in s["words"] for t in (w["start"], w["end"])]
    assert times == sorted(times)


def test_tighten_segment_cuts_video_and_writes_retimed_transcript(tmp_path):
    import json
    import shutil
    import subprocess
    import pytest
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg not installed")
    seg = tmp_path / "seg_0.mp4"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25:duration=3.6",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3.6", "-shortest", str(seg)],
                   check=True, capture_output=True)
    hi = {"start": 0.0, "end": 3.6}
    res = tighten_segment(str(seg), hi, [(0.0, 1.0), (2.5, 3.6)], {"segments": SEGMENTS}, str(tmp_path), 0,
                          padding=0.0, min_gap=0.0)
    video, subs, dur = res
    assert abs(dur - 2.1) < 0.01
    words = [w["word"].strip() for s in json.load(open(subs))["segments"] for w in s["words"]]
    assert "cats" not in words and "So" in words  # 1.6-2.0 was in the cut gap
    assert tighten_segment(str(seg), hi, [(0.0, 3.6)], {"segments": SEGMENTS}, str(tmp_path), 1) is None
