from engine.highlight_bench import run
from engine.highlight_quality import sentence_spans, snap_clip, snap_highlights


def _t(*sentences, gap=0.6, wd=0.3):
    """Transcript from sentences; returns (transcript, [(start, end)])"""
    t, segs, spans = 0.0, [], []
    for text in sentences:
        words, s = [], t
        for w in text.split():
            words.append({"word": " " + w, "start": round(t, 2), "end": round(t + wd, 2)})
            t += wd + 0.02
        segs.append({"start": round(s, 2), "end": round(words[-1]["end"], 2), "text": text, "words": words})
        spans.append((round(s, 2), round(words[-1]["end"], 2)))
        t += gap
    return {"segments": segs}, spans


def test_sentence_spans_split_on_punctuation_but_not_decimals_or_titles():
    tr, _ = _t("Pi is 3.14 and Dr. Smith agrees.", "Next one starts here!", "Third sentence ends now?")
    spans = sentence_spans(tr)
    assert [s[2].split()[0] for s in spans] == ["Pi", "Next", "Third"]


def test_pause_splits_sentences_even_without_punctuation():
    tr, _ = _t("no punctuation here at all", "second thought begins", gap=1.2)
    assert len(sentence_spans(tr)) == 2


def test_start_mid_sentence_moves_to_the_sentence_start_and_end_finishes_the_thought():
    tr, sp = _t("This is the first sentence of the story.", "Here comes the important part of it all.",
                "And this is the payoff that matters most.", "A closing remark that nobody needs.")
    clip = {"start": sp[1][0] + 1.0, "end": sp[2][0] + 1.0, "viral_score": 80}      # mid-sentence both sides
    out = snap_clip(clip, sentence_spans(tr), min_len=3.0)
    assert abs(out["start"] - sp[1][0]) < 0.06 or abs(out["start"] - sp[2][0]) < 0.06
    assert out["end"] >= sp[2][1]                                                    # the payoff sentence is finished
    assert out["end"] <= sp[3][0]                                                    # ... but the tail never enters the next one
    assert out["snapped"] and out["orig_start"] == round(clip["start"], 2)


def test_leading_filler_sentence_is_skipped():
    tr, sp = _t("So, um, okay.", "The real point begins right here today.", "And it keeps going for a while longer.", "Final words.")
    out = snap_clip({"start": sp[0][0], "end": sp[2][1]}, sentence_spans(tr), min_len=3.0)
    assert abs(out["start"] - sp[1][0]) < 0.06


def test_no_words_means_the_clip_is_left_alone():
    clip = {"start": 10.0, "end": 40.0}
    assert snap_clip(clip, []) == clip
    assert snap_highlights([clip], {"segments": []}) == [clip]


def test_neighbouring_clips_never_overlap_after_snapping():
    tr, sp = _t(*[f"Sentence number {i} has a few words in it." for i in range(12)])
    clips = [{"start": sp[1][0] + 0.7, "end": sp[5][1] - 0.5}, {"start": sp[4][0] + 0.4, "end": sp[9][1] - 0.6}]
    out = sorted(snap_highlights(clips, tr, min_len=3.0), key=lambda c: c["start"])
    assert out[0]["end"] <= out[1]["start"]


def test_max_length_is_respected():
    tr, sp = _t(*[f"Sentence number {i} has quite a few words in it today." for i in range(30)], wd=0.4)
    out = snap_clip({"start": sp[2][0], "end": sp[28][1]}, sentence_spans(tr))
    assert out["end"] - out["start"] <= 59.9


def test_benchmark_snapping_beats_raw_picks():
    # synthetic, seeded transcripts with labelled best moments and LLM-style sloppy edges (engine/highlight_bench.py)
    raw, snapped = run(snap_highlights, seeds=range(20))
    assert snapped["start_on_sentence"] >= 0.95 and raw["start_on_sentence"] < 0.3
    assert snapped["end_on_sentence"] >= 0.95 and raw["end_on_sentence"] < 0.5
    assert snapped["payoff_included"] >= 0.78 and snapped["payoff_included"] > raw["payoff_included"] + 0.3
    assert snapped["leadin_free"] >= 0.95
    assert snapped["duration_ok"] == 1.0
    assert snapped["iou"] >= raw["iou"] - 0.02          # snapping must not drift away from the labelled moment


def _long(n):
    return " ".join(f"word{i}" for i in range(n)) + "."


def test_start_inside_a_long_sentence_goes_back_to_its_beginning():
    # 50 words ~ 16 s: no sentence edge within 6 s of a start placed 10 s into it
    tr, sp = _t("Short opener here.", _long(50), "The next thought starts here.", "And it ends here.")
    clip = {"start": sp[1][0] + 10.0, "end": sp[3][1]}
    out = snap_clip(clip, sentence_spans(tr))
    assert abs(out["start"] - sp[1][0]) < 0.06


def test_overlapping_clips_are_split_at_a_sentence_not_mid_sentence():
    tr, sp = _t("First idea is stated in full here now.", "Second idea also gets its own sentence.", _long(40),
                "Closing words of the long part.")
    a = {"start": sp[0][0], "end": sp[2][0] + 8.0}            # runs into the long sentence
    b = {"start": sp[2][0] + 5.0, "end": sp[3][1]}            # starts inside it
    out = sorted(snap_highlights([a, b], tr, min_len=3.0), key=lambda c: c["start"])
    spans = sentence_spans(tr)
    ends = [e for _, e, _ in spans]
    starts = [s for s, _, _ in spans]
    assert out[0]["end"] <= out[1]["start"]
    assert any(0 <= out[0]["end"] - e <= 0.45 for e in ends)          # the earlier clip ends after a whole sentence
    assert any(abs(out[1]["start"] - s) < 0.06 for s in starts)        # the later one starts on a sentence
