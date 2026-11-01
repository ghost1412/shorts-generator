"""Prompt-based clip search: "find every moment where they talk about pricing".

`find_moments` returns highlight dicts in the same shape as `identify_highlights`
(start, end, viral_score, hook_text, reason), ranked by relevance to the query.
It asks an LLM to pick transcript windows; when no LLM is reachable it falls back to
keyword overlap so the flag still does something useful offline.
"""
import re

WINDOW_SECONDS = 15.0
CHUNK_WINDOWS = 200  # windows per LLM call, keeps each prompt well inside context limits
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have how i in is it its of on or that the their them "
    "they this to was we what when where which who why will with you your about talk talks talking".split()
)


def build_windows(segments, window=WINDOW_SECONDS):
    """Merge Whisper segments into ~`window`-second blocks: [{'start','end','text'}]."""
    windows = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if windows and seg["end"] - windows[-1]["start"] <= window:
            windows[-1]["end"] = seg["end"]
            windows[-1]["text"] += " " + text
        else:
            windows.append({"start": float(seg["start"]), "end": float(seg["end"]), "text": text})
    return windows


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in _STOPWORDS and len(t) > 1]


def keyword_matches(windows, query):
    """Offline fallback: [(window_index, score 1-10, reason)] for windows sharing words with the query."""
    q = set(_tokens(query))
    if not q:
        return []
    hits = []
    for i, w in enumerate(windows):
        overlap = q & set(_tokens(w["text"]))
        if overlap:
            hits.append((i, round(10 * len(overlap) / len(q), 1), "keywords: " + ", ".join(sorted(overlap))))
    return hits


def llm_matches(windows, query, ask):
    """Ask the LLM which windows match. `ask(prompt) -> parsed JSON`. Returns [(idx, score, reason)]."""
    hits = []
    for base in range(0, len(windows), CHUNK_WINDOWS):
        chunk = windows[base:base + CHUNK_WINDOWS]
        listing = "\n".join(f"[{base + i}] ({w['start']:.0f}s) {w['text'][:400]}" for i, w in enumerate(chunk))
        prompt = (
            f"Find every part of this transcript that matches the request: \"{query}\"\n\n"
            f"Transcript windows (index, start time, text):\n{listing}\n\n"
            "Return ONLY a JSON list. Each item: {\"index\": <window index>, \"score\": <relevance 1-10>, "
            "\"reason\": \"<short why>\"}. Include only windows that genuinely match; return [] if none do."
        )
        parsed = ask(prompt)
        if isinstance(parsed, dict):
            parsed = parsed.get("matches") or parsed.get("results") or []
        for item in parsed or []:
            try:
                idx, score = int(item["index"]), float(item.get("score", 5))
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= idx < len(windows) and score >= 4:
                hits.append((idx, min(score, 10.0), str(item.get("reason", ""))[:140]))
    return hits


def _group_hits(hits, windows, target_duration, min_duration):
    """Merge adjacent matching windows, pad to min_duration and cap at target_duration."""
    hits = sorted(hits)
    groups = []
    for idx, score, reason in hits:
        if groups and idx - groups[-1]["last"] <= 1:
            g = groups[-1]
            g["last"] = idx
            g["scores"].append(score)
        else:
            groups.append({"first": idx, "last": idx, "scores": [score], "reason": reason})
    total_end = windows[-1]["end"]
    clips = []
    for g in groups:
        start, end = windows[g["first"]]["start"], windows[g["last"]]["end"]
        if end - start > target_duration:  # keep the start of the topic, trim the tail
            end = start + target_duration
        if end - start < min_duration:  # pad symmetrically
            pad = (min_duration - (end - start)) / 2
            start, end = max(0.0, start - pad), min(total_end, end + pad)
        relevance = max(g["scores"])
        clips.append({
            "start": round(start, 2), "end": round(end, 2),
            "viral_score": round(relevance * 10), "hook_text": g["reason"] or "Match",
            "reason": f"Matches '{{query}}': {g['reason']}".strip(": "),
            "relevance": relevance,
        })
    return clips


def find_moments(segments, query, clip_count=5, target_duration=45, min_duration=15, ask=None):
    """Return up to `clip_count` highlight dicts for `query`, best match first."""
    windows = build_windows(segments)
    if not windows or not (query or "").strip():
        return []
    hits = []
    if ask is not None:
        try:
            hits = llm_matches(windows, query, ask)
        except Exception as e:  # any provider failure -> offline fallback
            print(f"[Warning] LLM moment search failed ({e}); using keyword matching.")
    if not hits:
        hits = keyword_matches(windows, query)
    clips = _group_hits(hits, windows, target_duration, min_duration)
    for c in clips:
        c["reason"] = c["reason"].replace("{query}", query)
        if c["hook_text"].startswith("keywords:"):  # on-screen hook should read like a title, not a debug string
            c["hook_text"] = query.strip()[:40]
    clips.sort(key=lambda c: c["relevance"], reverse=True)
    return clips[:clip_count]


def llm_ask():
    """Default `ask` backed by the project's provider chain (Gemini -> Ollama -> HuggingFace)."""
    from engine.script_gen import get_llm_response, robust_json_parse

    def ask(prompt):
        raw = get_llm_response(prompt, "You search transcripts. Respond with raw JSON only.", max_tokens=3000)
        return robust_json_parse(raw)

    return ask
