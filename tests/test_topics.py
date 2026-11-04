from collections import Counter

from engine.topics import content_words, cosine, diversify, topic_of, topic_segments


def _transcript(blocks, per=20, wd=0.3, gap=0.6):
    """blocks = list of vocab strings; each yields `per` sentences built from that vocabulary. Returns (transcript, [(start, end) per block])."""
    t, segs, spans = 0.0, [], []
    for b, vocab in enumerate(blocks):
        words_pool = vocab.split()
        b_start = t
        for i in range(per):
            ws = [words_pool[(i * 3 + k) % len(words_pool)] for k in range(8)]
            words, s = [], t
            for w in ws:
                words.append({"word": " " + w + ("." if w is ws[-1] else ""), "start": round(t, 2), "end": round(t + wd, 2)})
                t += wd + 0.02
            segs.append({"start": round(s, 2), "end": round(words[-1]["end"], 2), "text": " ".join(ws) + ".", "words": words})
            t += gap
        spans.append((b_start, t))
    return {"segments": segs}, spans


MONEY = "budget subscriptions savings account interest invest compound dollars monthly expenses cancel income salary"
SPACE = "telescope galaxy orbit planet nebula astronomer rocket gravity satellite comet asteroid cosmos stellar"


def test_content_words_drop_stopwords_and_short_words():
    assert content_words("The cat and a dog are in it") == ["cat", "dog"]


def test_cosine_basics():
    a, b = Counter("money budget savings".split()), Counter("planet orbit galaxy".split())
    assert cosine(a, a) > 0.99 and cosine(a, b) == 0.0 and cosine(Counter(), a) == 0.0


def test_topic_segments_find_the_switch():
    tr, spans = _transcript([MONEY, SPACE])
    topics = topic_segments(tr)
    assert len(topics) == 2
    assert abs(topics[0][1] - spans[0][1]) < 8.0                      # the cut sits near where the subject changes
    assert topic_of(topics, spans[0][0] + 5, spans[0][0] + 20) == 0 and topic_of(topics, spans[1][0] + 5, spans[1][0] + 20) == 1


def test_near_duplicates_are_dropped_and_a_new_topic_gets_a_slot():
    # the speaker makes the same money point twice (clips 1 and 2) and talks about space in between (clip 3)
    tr, spans = _transcript([MONEY, SPACE, MONEY])
    m1, sp, m2 = spans
    cands = [{"start": m1[0] + 2, "end": m1[0] + 30, "final_score": 90},
             {"start": m2[0] + 2, "end": m2[0] + 30, "final_score": 89},      # same wording as clip 1
             {"start": sp[0] + 2, "end": sp[0] + 30, "final_score": 70}]
    out = diversify(cands, tr)
    assert [round(c["final_score"]) for c in out] == [90, 70]               # the repeat is gone, the space clip stays


def test_a_slightly_weaker_clip_on_a_new_topic_beats_a_repeat_in_the_same_topic():
    tr, spans = _transcript([MONEY, SPACE])
    m, sp = spans
    same = {"start": m[0] + 30, "end": m[0] + 55, "final_score": 85}
    other = {"start": sp[0] + 2, "end": sp[0] + 27, "final_score": 80}
    top = {"start": m[0] + 2, "end": m[0] + 27, "final_score": 90}
    order = diversify([top, same, other], tr, dup_threshold=0.99)           # no dropping, only re-ordering
    assert order[0]["final_score"] == 90 and order[1]["final_score"] == 80


def test_input_is_not_modified_and_tiny_inputs_pass_through():
    tr, spans = _transcript([MONEY, SPACE])
    one = [{"start": 1.0, "end": 20.0, "final_score": 50}]
    assert diversify(one, tr) == one
    cands = [{"start": spans[0][0] + 2, "end": spans[0][0] + 20, "final_score": 80}, {"start": spans[1][0] + 2, "end": spans[1][0] + 20, "final_score": 70}]
    before = [dict(c) for c in cands]
    diversify(cands, tr)
    assert cands == before


def test_works_without_word_timings():
    tr = {"segments": [{"start": i * 5.0, "end": i * 5.0 + 4, "text": f"budget savings account number {i}."} for i in range(30)]}
    cands = [{"start": 0, "end": 20, "final_score": 80}, {"start": 60, "end": 80, "final_score": 79}]
    assert len(diversify(cands, tr)) >= 1                                   # near-identical wording: second may be dropped, never a crash
