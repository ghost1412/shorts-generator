import json

from engine.highlight_quality import sentence_spans
from engine.highlight_rank import build_prompt, parse_ranking, rank_with_context


def _t(sentences, gap=0.6, wd=0.3):
    t, segs = 0.0, []
    for text in sentences:
        words, s = [], t
        for w in text.split():
            words.append({"word": " " + w, "start": round(t, 2), "end": round(t + wd, 2)})
            t += wd + 0.02
        segs.append({"start": round(s, 2), "end": round(words[-1]["end"], 2), "text": text, "words": words})
        t += gap
    return {"segments": segs}


SENT = [f"Sentence number {i} says something fairly interesting about topic {i}." for i in range(20)]


def _cands(tr):
    sp = sentence_spans(tr)
    return [{"start": sp[2][0], "end": sp[5][1], "final_score": 70, "viral_score": 70},
            {"start": sp[8][0], "end": sp[11][1], "final_score": 60, "viral_score": 60}], sp


def test_prompt_has_context_for_every_candidate():
    tr = _t(SENT)
    cands, sp = _cands(tr)
    p = build_prompt(cands, sp, sp[-1][1])
    assert "CLIP 1" in p and "CLIP 2" in p and p.count("before:") == 2 and p.count("after:") == 2
    assert "Sentence number 1 " in p                  # the sentence before clip 1
    assert "extend_end" in p and "JSON" in p


def test_scores_are_blended_and_order_follows_the_llm():
    tr = _t(SENT)
    cands, _ = _cands(tr)
    reply = json.dumps([{"id": 1, "score": 4, "complete": True, "extend_end": 0, "trim_start": 0, "reason": "meh"},
                        {"id": 2, "score": 9, "complete": True, "extend_end": 0, "trim_start": 0, "reason": "great"}])
    out = rank_with_context(cands, tr, ask=lambda p: reply)
    assert out[0]["llm_score"] == 9 and out[0]["llm_reason"] == "great"
    assert out[0]["final_score"] == round(0.6 * 90 + 0.4 * 60, 1)                  # 60% LLM + 40% first-pass score
    assert out[0]["viral_score"] == int(round(out[0]["final_score"])) and out[0]["ranked_in_context"]


def test_extend_end_and_trim_start_move_whole_sentences():
    tr = _t(SENT)
    cands, sp = _cands(tr)
    reply = json.dumps([{"id": 1, "score": 8, "extend_end": 1, "trim_start": 1},
                        {"id": 2, "score": 7, "extend_end": 0, "trim_start": 0}])
    out = {round(h["llm_score"]): h for h in rank_with_context(cands, tr, ask=lambda p: reply)}
    assert out[8]["end"] == round(sp[6][1], 2) and out[8]["start"] == round(sp[3][0], 2) and out[8]["edges_adjusted"]
    assert out[7]["start"] == round(sp[8][0], 2) and "edges_adjusted" not in out[7]


def test_extend_is_refused_when_the_clip_would_be_too_long():
    tr = _t([f"This sentence has quite a few more words than the others, number {i}." for i in range(30)], wd=0.45)
    sp = sentence_spans(tr)
    cands = [{"start": sp[0][0], "end": sp[8][1], "final_score": 70}]            # already ~59 s
    assert cands[0]["end"] - cands[0]["start"] <= 59.9
    reply = json.dumps([{"id": 1, "score": 8, "extend_end": 2}])
    out = rank_with_context(cands, tr, ask=lambda p: reply)
    assert out[0]["end"] == cands[0]["end"] and "edges_adjusted" not in out[0]     # one more sentence would pass a minute


def test_garbage_or_failure_returns_none_so_the_old_scoring_runs():
    tr = _t(SENT)
    cands, _ = _cands(tr)
    assert rank_with_context(cands, tr, ask=lambda p: "I cannot rate these, sorry") is None
    assert rank_with_context(cands, tr, ask=lambda p: json.dumps([{"id": 9, "score": 5}])) is None   # ids that do not exist

    def boom(p):
        raise RuntimeError("no provider")
    assert rank_with_context(cands, tr, ask=boom) is None
    assert rank_with_context([], tr, ask=lambda p: "[]") is None
    assert rank_with_context(cands, {"segments": []}, ask=lambda p: "[]") is None


def test_parse_accepts_wrapped_json_and_odd_values():
    reply = '```json\n{"clips": [{"id": "2", "score": "7.5", "extend_end": "one", "trim_start": true, "reason": "x"}]}\n```'
    got = parse_ranking(reply, 2)
    assert got[1]["score"] == 7.5 and got[1]["extend_end"] == 0 and got[1]["trim_start"] == 1
    assert parse_ranking("[]", 2) == {} and parse_ranking({"clips": []}, 2) == {}
