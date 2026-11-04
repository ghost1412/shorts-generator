"""Second-pass ranking of highlight candidates with context.

The first pass proposes moments from coarse transcript windows. This pass shows the LLM ALL the candidates in ONE request,
together with a short overview of the whole video and, for every candidate, the sentence before and the sentence after it.
That lets it judge what a clip alone cannot show: is the payoff inside the clip or in the next sentence, is the first
sentence just throat-clearing, and which candidates are the strongest relative to each other.

It returns the candidates re-scored and with their edges adjusted by whole sentences (end later / start later), or None when
no LLM answers or the reply is unusable, so the caller keeps the older per-clip scoring. One call instead of one per clip
also costs less.
"""
import json

from engine.highlight_quality import sentence_spans

SYSTEM = "You are a viral short-form video editor. Reply with raw JSON only."
MAX_LEN = 59.9
MIN_LEN = 8.0


def _text_in(spans, start, end):
    return " ".join(t for s, e, t in spans if e > start + 0.05 and s < end - 0.05).strip()


def overview(spans, total, max_chars=700):
    """A few evenly spaced sentences so the model knows what the whole video is about."""
    if not spans:
        return ""
    step = max(1, len(spans) // 10)
    pieces = [f"[{int(s)}s] {t}" for s, _, t in spans[::step]]
    return (f"Video length {int(total)}s. Sampled lines: " + " | ".join(pieces))[:max_chars]


def build_prompt(candidates, spans, total):
    lines = []
    for i, h in enumerate(candidates, 1):
        s, e = float(h["start"]), float(h["end"])
        before = next((t for ss, ee, t in reversed(spans) if ee <= s + 0.05), "")
        after = next((t for ss, ee, t in spans if ss >= e - 0.05), "")
        lines.append(f"CLIP {i} ({s:.0f}s-{e:.0f}s, {e - s:.0f}s long)\n"
                     f"  before: {before[:160]}\n  CLIP TEXT: {_text_in(spans, s, e)[:650]}\n  after: {after[:160]}")
    return (
        f"{overview(spans, total)}\n\nCandidate clips for YouTube Shorts / TikTok:\n\n" + "\n\n".join(lines) + "\n\n"
        "Rate every clip. Reply with a JSON list, one object per clip, exactly:\n"
        '[{"id": 1, "score": <1-10 viral potential vs the other clips>, "complete": <true if the payoff / end of the thought is '
        'inside the clip>, "extend_end": <0, 1 or 2 sentences to add at the end so the payoff is included>, '
        '"trim_start": <0 or 1: 1 if the first sentence is throat-clearing and should be dropped>, "reason": "<short>"}]\n'
        "Use the full 1-10 range; do not give every clip the same score."
    )


def _small_int(value, lo, hi):
    """value as an int clamped to lo..hi; true/false count as 1/0, anything unreadable is 0."""
    if isinstance(value, bool):
        return int(value) if lo <= int(value) <= hi else 0
    try:
        return max(lo, min(hi, int(float(value))))
    except (TypeError, ValueError):
        return 0


def parse_ranking(raw, n):
    """{index (0-based): {score, extend_end, trim_start, complete, reason}} from the model's reply, or {} when unusable."""
    try:
        from engine.script_gen import robust_json_parse
        data = robust_json_parse(raw) if isinstance(raw, str) else raw
    except Exception:
        try:
            data = json.loads(raw)
        except Exception:
            return {}
    if isinstance(data, dict):
        data = data.get("clips") or data.get("ranking") or data.get("results") or []
    out = {}
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id")) - 1
            score = float(item.get("score"))
        except (TypeError, ValueError):
            continue
        if not 0 <= idx < n:
            continue
        out[idx] = {
            "score": max(1.0, min(10.0, score)),
            "extend_end": _small_int(item.get("extend_end"), 0, 2),
            "trim_start": _small_int(item.get("trim_start"), 0, 1),
            "complete": item.get("complete"),
            "reason": str(item.get("reason") or "")[:160],
        }
    return out


def _adjust_edges(h, spans, info):
    """Whole-sentence edge moves the model asked for, kept inside the short-length limits."""
    start, end = float(h["start"]), float(h["end"])
    new_start, new_end = start, end
    if info["extend_end"]:
        last = max((i for i, (s, e, t) in enumerate(spans) if s < end - 0.05), default=None)
        if last is not None:
            target = spans[min(len(spans) - 1, last + info["extend_end"])][1]
            if target > end and target - start <= MAX_LEN:
                new_end = target
    if info["trim_start"]:
        first = next((i for i, (s, e, t) in enumerate(spans) if s >= start - 0.3), None)
        if first is not None and first + 1 < len(spans):
            cand = spans[first + 1][0]
            if cand > start and new_end - cand >= MIN_LEN:
                new_start = cand
    return new_start, new_end


def rank_with_context(highlights, transcript, ask=None, max_candidates=10, weight=0.6):
    """Re-scored copies of `highlights` (best first), or None when the LLM pass could not be used."""
    if not highlights:
        return None
    spans = sentence_spans(transcript)
    if not spans:
        return None
    candidates = sorted(highlights, key=lambda h: float(h.get("final_score", h.get("viral_score", 0)) or 0), reverse=True)[:max_candidates]
    total = spans[-1][1]
    if ask is None:
        from engine.script_gen import get_llm_response

        def ask(prompt):
            return get_llm_response(prompt, SYSTEM, max_tokens=900)
    try:
        raw = ask(build_prompt(candidates, spans, total))
    except Exception as e:
        print(f"[Warning] Context ranking skipped ({e}).")
        return None
    info = parse_ranking(raw, len(candidates))
    if len(info) < max(1, len(candidates) // 2):          # most clips unrated: the reply is not trustworthy
        print("[Warning] Context ranking reply was unusable; keeping the per-clip scoring.")
        return None
    out = []
    for i, h in enumerate(candidates):
        h = dict(h)
        base = float(h.get("final_score", h.get("viral_score", 50)) or 50)
        if i in info:
            r = info[i]
            blended = round(weight * r["score"] * 10.0 + (1.0 - weight) * base, 1)
            h.update({"llm_score": r["score"], "llm_reason": r["reason"], "final_score": blended, "score": blended,
                      "viral_score": int(round(blended)), "ranked_in_context": True})
            new_start, new_end = _adjust_edges(h, spans, r)
            if (new_start, new_end) != (float(h["start"]), float(h["end"])):
                h.update({"start": round(new_start, 2), "end": round(new_end, 2), "edges_adjusted": True})
        out.append(h)
    out.sort(key=lambda h: float(h.get("final_score", 0)), reverse=True)
    n_adj = sum(1 for h in out if h.get("edges_adjusted"))
    print(f"[Log] Context ranking: rated {len(info)} of {len(candidates)} candidates in one request; {n_adj} edge(s) adjusted.")
    return out
