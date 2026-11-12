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


def _five_second_sentences(n=20):
    return _t(*[f"sentence number {i} has exactly these words in it okay done now and here ends." for i in range(n)], gap=0.4)


def _no_overlaps(clips):
    cs = sorted(clips, key=lambda c: c["start"])
    return all(a["end"] <= b["start"] for a, b in zip(cs, cs[1:]))


def test_three_overlapping_clips_end_with_no_overlap_and_no_stubs():
    tr, _ = _five_second_sentences()
    for raw in ([{"start": 0, "end": 30}, {"start": 5, "end": 60}, {"start": 20, "end": 45}],
                [{"start": 10, "end": 40}, {"start": 10, "end": 30}],
                [{"start": 0, "end": 30}, {"start": 20, "end": 60}, {"start": 25, "end": 40}]):
        out = snap_highlights(raw, tr, min_len=8.0)
        assert out and _no_overlaps(out), (raw, out)
        assert all(c["end"] - c["start"] >= 8.0 for c in out), (raw, out)


def test_a_user_moment_is_never_trimmed_by_an_overlap():
    tr, _ = _five_second_sentences()
    out = snap_highlights([{"start": 10, "end": 40, "user_moment": True}, {"start": 30, "end": 60}], tr, min_len=8.0)
    mine = next(c for c in out if c.get("user_moment"))
    assert (mine["start"], mine["end"]) == (10, 40)
    assert _no_overlaps(out)


def test_long_mode_options_keep_long_moments_whole():
    tr, sp = _five_second_sentences(30)
    out = snap_highlights([{"start": sp[2][0] + 1.0, "end": sp[22][0] + 1.0}], tr, min_len=8.0, max_len=180.0)
    assert out[0]["end"] - out[0]["start"] > 60                          # a highlights-reel moment is not cut to a short's minute
    assert any(abs(out[0]["start"] - s) < 0.06 for s, _ in sp)


def test_fit_to_target_never_leaves_a_piece_below_the_floor():
    from engine.analysis import fit_to_target
    hs = [{"start": 0, "end": 200, "viral_score": 90}, {"start": 300, "end": 340, "viral_score": 80}]
    out = fit_to_target(hs, 220, min_len=25.0)
    assert all(h["end"] - h["start"] >= 25.0 for h in out)
    assert sum(h["end"] - h["start"] for h in out) <= 220 * 1.08 + 1e-6


def test_moments_seconds_apart_are_joined_but_user_moments_are_not():
    from engine.highlight_quality import merge_close_moments
    out = merge_close_moments([{"start": 0, "end": 20}, {"start": 21.5, "end": 40}, {"start": 60, "end": 80}])
    assert [(h["start"], h["end"]) for h in out] == [(0, 40), (60, 80)]
    kept = merge_close_moments([{"start": 0, "end": 20, "user_moment": True}, {"start": 21, "end": 40}])
    assert len(kept) == 2


def test_a_fallback_window_is_cut_to_the_asked_length():
    from engine.analysis import trim_to_target
    assert trim_to_target({"start": 10, "end": 55}, 30) == {"start": 10, "end": 40.0, "trimmed": True}
    assert trim_to_target({"start": 10, "end": 44}, 30) == {"start": 10, "end": 44}       # within 20%: left alone
    assert trim_to_target({"start": 10, "end": 55}, None) == {"start": 10, "end": 55}


def test_backfill_from_nothing_keeps_picks_apart():
    from engine.analysis import pick_backfill
    segs = [{"start": 445, "end": 480, "norm_score": 0.9}, {"start": 489, "end": 524, "norm_score": 0.85},
            {"start": 900, "end": 935, "norm_score": 0.5}]
    out = pick_backfill(segs, [], 2)
    assert [h["start"] for h in out] == [445, 900]        # the neighbour 9 s away is skipped while a far one exists


def test_a_mic_check_or_weak_opening_sentence_is_skipped_at_the_start():
    tr, spans = _t("Testing one, two, three testing.", "Whatever happens to your eyes is a zero G effect.",
                   "It has nothing to do with the air in the cabin at all.", "That is the whole story about the strange effect we saw.",
                   "Nobody expected the result to look like this at all.")
    out = snap_clip({"start": spans[0][0], "end": spans[4][1]}, sentence_spans(tr))
    assert abs(out["start"] - spans[1][0]) < 0.06


def test_a_clip_that_starts_on_and_skips_to_the_next_sentence():
    tr, spans = _t("And, and it just goes right into your mouth.", "Then more fluid comes up from below the line.",
                   "Nobody expected the result to look like this at all.", "A last sentence closes out the whole clip here today.")
    out = snap_clip({"start": spans[0][0], "end": spans[3][1]}, sentence_spans(tr))
    assert abs(out["start"] - spans[1][0]) < 0.06 or abs(out["start"] - spans[2][0]) < 0.06


def test_a_good_opening_is_left_alone():
    tr, spans = _t("Whatever happens to your eyes is a zero G effect.", "It has nothing to do with the air in the cabin at all.",
                   "That is the whole story about the strange effect we saw.")
    out = snap_clip({"start": spans[0][0], "end": spans[2][1]}, sentence_spans(tr))
    assert abs(out["start"] - spans[0][0]) < 0.06


def test_so_and_that_at_the_start_are_real_openings_but_connectives_are_not():
    from engine.highlight_quality import weak_opening
    assert not weak_opening("So I quit my job and moved to Japan.")
    assert not weak_opening("That is the single biggest mistake founders make.")
    assert not weak_opening("Can you hear the difference between the two?")
    assert weak_opening("So, the principle is simple.")
    assert weak_opening("And then it just kept going.")
    assert weak_opening("Can you hear me now?")
    assert weak_opening("Yeah. Testing one, two, three.")


def test_the_weak_opening_skip_does_not_add_up_when_a_clip_is_snapped_again():
    tr, spans = _t("And one thing leads on.", "And another follows right after that.", "And a third comes next as well.",
                   "And the fourth line closes the story out here today.", "Then a fifth sentence that ends the clip for good now.",
                   "Final words close it all out in the end of it.")
    clip = {"start": spans[0][0], "end": spans[5][1]}
    once = snap_clip(clip, sentence_spans(tr))
    twice = snap_clip(once, sentence_spans(tr))
    assert twice["start"] == once["start"]
    assert once["end"] - once["start"] >= 0.6 * (clip["end"] - clip["start"]) - 0.5      # never gives up more than 40%


def test_the_weaker_overlapping_clip_gives_way_not_the_better_earlier_one():
    tr, spans = _t("First sentence of the strong clip stands here.", "Second sentence of the strong clip stands here too.",
                   "Third sentence of the strong clip is the payoff line.", "Fourth sentence belongs to the weaker clip only now.",
                   "Fifth sentence of the weaker clip wraps up the whole thing.")
    strong = {"start": spans[0][0], "end": spans[2][1], "final_score": 95}
    weak = {"start": spans[1][0] + 0.1, "end": spans[4][1], "final_score": 40}
    out = snap_highlights([strong, weak], tr, min_len=1.0)
    best = next(c for c in out if c.get("final_score") == 95)
    assert best["end"] >= spans[2][1] - 0.01                       # the strong clip keeps its payoff sentence
    assert all(a["end"] <= b["start"] + 0.01 for a, b in zip(sorted(out, key=lambda c: c["start"]), sorted(out, key=lambda c: c["start"])[1:]))


def test_a_clip_does_not_end_on_a_sentence_that_trails_off():
    tr, spans = _t("Whatever happens to your eyes is a zero G effect we measured.", "It has nothing to do with the air in the cabin at all.",
                   "That is the whole story about the strange effect we saw.", "We looked at the results of the places that...",
                   "A later sentence that the clip never reaches at all here.")
    clip = {"start": spans[0][0], "end": spans[3][1]}
    out = snap_clip(clip, sentence_spans(tr))
    assert out["end"] <= spans[2][1] + 0.5 and out["end"] > spans[1][1]       # ends on the sentence before the dangling one
    again = snap_clip(out, sentence_spans(tr))
    assert again["end"] == out["end"]                                          # snapping again changes nothing


def test_a_trailing_off_ending_is_kept_when_dropping_it_would_cost_too_much():
    tr, spans = _t("Short opening line here for the clip itself.", "A very long second sentence that carries almost the whole clip with many many words in it.",
                   "We looked at the places that...")
    clip = {"start": spans[0][0], "end": spans[2][1]}
    out = snap_clip(clip, sentence_spans(tr), min_len=1.0)
    assert out["end"] >= spans[1][1] - 0.01


def test_snapping_twice_keeps_the_original_pick_for_the_move_count():
    tr, spans = _t("First sentence of the clip stands here today.", "Second sentence follows right after the first one.",
                   "Third sentence closes the whole clip out here today.", "A fourth sentence the clip never reaches at all here.")
    clip = {"start": spans[0][0] + 1.0, "end": spans[2][1] - 0.5}
    once = snap_clip(clip, sentence_spans(tr))
    twice = snap_clip(once, sentence_spans(tr))
    assert once["orig_start"] == twice["orig_start"] == round(clip["start"], 2)
    assert once["orig_end"] == twice["orig_end"] == round(clip["end"], 2)


def test_complete_sentences_are_never_called_trailing_off():
    from engine.highlight_quality import trails_off_end
    for s in ("Look at this.", "Yes we can.", "That is what I was talking about.", "And that is what I am most proud of.", "You know what?", "Take vitamin A.", "It is Plan A."):
        assert not trails_off_end(s), s
    assert trails_off_end("We looked at the places that...")          # Whisper's ellipsis after a word that needs a continuation
    assert trails_off_end("We looked at the results of the.")         # no complete sentence ends on "the"
    assert trails_off_end("He said and")


def test_a_clip_ending_on_a_complete_stranded_preposition_keeps_its_payoff():
    tr, spans = _t("Whatever happens to your eyes is a zero G effect we measured.", "It has nothing to do with the air in the cabin at all.",
                   "That is the whole story and that is what I am most proud of.")
    clip = {"start": spans[0][0], "end": spans[2][1]}
    out = snap_clip(clip, sentence_spans(tr))
    assert out["end"] >= spans[2][1] - 0.01


def test_the_better_clip_keeps_its_payoff_even_when_the_weaker_one_is_too_short_to_give_way():
    tr, spans = _t("First sentence of the strong clip stands here today.", "Second sentence of the strong clip stands here too.",
                   "Third sentence of the strong clip is the payoff line.", "Fourth sentence of the weaker clip only.")
    strong = {"start": spans[0][0], "end": spans[2][1], "final_score": 95}
    weak = {"start": spans[2][0] + 0.1, "end": spans[3][1], "final_score": 40}
    out = snap_highlights([strong, weak], tr, min_len=3.0)
    best = next(c for c in out if c.get("final_score") == 95)
    assert best["end"] >= spans[2][1] - 0.01                                  # the strong clip is not trimmed
    assert all(a["end"] <= b["start"] + 0.01 for a, b in zip(sorted(out, key=lambda c: c["start"]), sorted(out, key=lambda c: c["start"])[1:]))


def test_japanese_and_hindi_sentences_split_without_spaces():
    tr = {"segments": [{"start": 0.0, "end": 12.0, "text": "これは最初の文です。これは二番目の文です。三番目の文もあります。"},
                       {"start": 20.0, "end": 30.0, "text": "यह पहला वाक्य है। यह दूसरा वाक्य है।"}]}
    texts = [s[2] for s in sentence_spans(tr)]
    assert len(texts) == 5 and texts[0].endswith("。") and texts[3].endswith("।")


def test_the_weaker_clip_without_a_sentence_start_left_does_not_open_mid_sentence():
    tr, spans = _t("First sentence of the strong clip stands here.", "Second sentence of the strong clip stands here too.",
                   "Third sentence is long and shared by both of the clips here.")
    strong = {"start": spans[0][0], "end": spans[1][1], "final_score": 95}
    weak = {"start": spans[1][0] + 0.1, "end": spans[2][1], "final_score": 40}
    out = snap_highlights([strong, weak], tr, min_len=1.0)
    starts = [s for s, _ in spans]
    assert all(any(abs(c["start"] - st) < 0.06 for st in starts) for c in out)      # every clip still opens on a sentence start
    srt = sorted(out, key=lambda c: c["start"])
    assert all(a["end"] <= b["start"] + 0.01 for a, b in zip(srt, srt[1:]))
