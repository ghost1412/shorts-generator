"""YouTube chapters for the long-form highlights video.

YouTube only turns a timestamp list in the description into chapters when it starts at 0:00, has at least three entries and
every chapter is at least 10 seconds long. The reel is built from highlight segments played in order with a short crossfade
between them, so each segment's place on the reel timeline is known: segment k starts at (sum of the earlier lengths) minus
k crossfades. Titles come from what is said in each chapter (LLM), with a keyword fallback when no LLM answers.
"""
import re

MIN_CHAPTER = 10.0
MIN_CHAPTERS = 3
MAX_CHAPTERS = 12
TITLE_MAX = 48
_STOP = set("""a an and are as at be but by for from had has have he her his i if in is it its just like me my no not of on or
our out she so than that the their them then there these they this to too up us was we were what when which who will with you
your yeah okay um uh gonna got get going know really very about into over also took said says say thing things people ask first
now back here right good great well one all can do does did would could should much many some more most other because still even way
make made see look want need think thought let lot time come came go went yes sure actually basically excellent amazing""".split())


def reel_timeline(highlights, xf=0.25, durations=None):
    """[(start, end)] on the reel timeline for each highlight in play order. `durations` are the rendered segment lengths
    when known, otherwise end - start of each highlight."""
    out, offset = [], 0.0
    for i, h in enumerate(highlights):
        d = float(durations[i]) if durations and i < len(durations) else max(0.0, float(h.get("end", 0)) - float(h.get("start", 0)))
        out.append((offset, offset + d))
        offset += d - (xf if i < len(highlights) - 1 else 0.0)
    return out


def build_chapters(highlights, xf=0.25, total=None, durations=None, min_len=MIN_CHAPTER, max_chapters=MAX_CHAPTERS):
    """Group consecutive highlight segments into chapters. Returns [{"start": s, "end": e, "segments": [indexes]}] starting at
    0.0, every chapter >= `min_len` long, or [] when the reel is too short for three chapters.

    `total` is the real length of the rendered reel: when given, the timeline is scaled to it (tightening or re-encoding can
    make the file a little shorter or longer than end - start of each highlight).
    """
    if not highlights:
        return []
    spans = reel_timeline(highlights, xf, durations)
    nominal = spans[-1][1]
    if total and nominal > 0:
        k = float(total) / nominal
        spans = [(s * k, e * k) for s, e in spans]
    # walk the segments in order and close a chapter once it is long enough (the next one starts one crossfade earlier than
    # this one ends, hence the margin); a short tail joins the last chapter
    chapters, cur = [], None
    for i, (s, e) in enumerate(spans):
        if cur is None:
            cur = {"start": s, "end": e, "segments": [i]}
        else:
            cur["end"] = e
            cur["segments"].append(i)
        if cur["end"] - cur["start"] - xf >= min_len:
            chapters.append(cur)
            cur = None
    if cur is not None:
        if chapters:
            chapters[-1]["end"] = cur["end"]
            chapters[-1]["segments"] += cur["segments"]
        else:
            chapters.append(cur)
    chapters[0]["start"] = 0.0
    # too many chapters: merge the shortest adjacent pair until within the limit
    while len(chapters) > max_chapters:
        i = min(range(len(chapters) - 1), key=lambda k: chapters[k + 1]["end"] - chapters[k]["start"])
        chapters[i] = {"start": chapters[i]["start"], "end": chapters[i + 1]["end"],
                       "segments": chapters[i]["segments"] + chapters[i + 1]["segments"]}
        del chapters[i + 1]
    if len(chapters) < MIN_CHAPTERS:
        return []
    return chapters


def chapter_text(chapter, highlights, transcript_segments, limit=600):
    """What is said in the source windows behind a chapter."""
    parts = []
    for idx in chapter["segments"]:
        h = highlights[idx]
        s, e = float(h.get("start", 0)), float(h.get("end", 0))
        parts.append(" ".join((seg.get("text") or "").strip() for seg in transcript_segments
                              if seg.get("end", 0) > s and seg.get("start", 0) < e))
    return " ".join(p for p in parts if p).strip()[:limit]


def keyword_title(text, max_len=TITLE_MAX):
    """Fallback title: the most frequent content words, in the order they first appear, capitalised ('Pricing, Subscription')."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", text or "")]
    counts, first = {}, {}
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in _STOP or "'" in lw or "\u2019" in lw:      # a contraction (I'm, that's, don't) is not a topic
            continue
        counts[lw] = counts.get(lw, 0) + 1
        first.setdefault(lw, i)
    if not counts:
        return ""
    top = sorted(counts, key=lambda w: (-counts[w], first[w]))[:3]
    top.sort(key=lambda w: first[w])
    title = ", ".join(w.capitalize() for w in top)
    return title[:max_len].rstrip(", ")


def _clean_title(t):
    t = re.sub(r"\s+", " ", str(t or "")).strip().strip('"').strip("'").rstrip(".")
    t = re.sub(r"^\d{1,2}[:.)]\d{0,2}\s*[-–—]?\s*", "", t)      # a timestamp the model repeated
    if len(t) > TITLE_MAX:
        cut = t[:TITLE_MAX].rsplit(" ", 1)[0]
        t = cut or t[:TITLE_MAX]
    return t


def llm_titles(texts, ask=None):
    """One title per chapter text from the LLM, or None when nothing usable came back."""
    if not any(texts):
        return None
    if ask is None:
        from engine.script_gen import get_llm_response, robust_json_parse

        def ask(prompt):
            return robust_json_parse(get_llm_response(prompt, temperature=0.4, max_tokens=700, timeout=40))
    listing = "\n".join(f'{i + 1}. "{t[:400]}"' for i, t in enumerate(texts))
    prompt = (
        "These are consecutive chapters of one video. For each chapter write a short, plain YouTube chapter title "
        f"(2-6 words, under {TITLE_MAX} characters, no timestamps, no quotes, no emoji) that says what the chapter is about. "
        "Use only what is said in the chapter; do not invent names, numbers or facts.\n"
        f"{listing}\n"
        f'Return ONLY JSON: {{"titles": ["...", ...]}} with exactly {len(texts)} titles in order.'
    )
    try:
        data = ask(prompt)
    except Exception as e:
        print(f"[Warning] Chapter titles from the LLM failed ({e}); using keywords.")
        return None
    titles = data.get("titles") if isinstance(data, dict) else data
    if not isinstance(titles, list) or len(titles) != len(texts):
        return None
    return [_clean_title(t) for t in titles]


def grounded_title(title, text):
    """True when the title's numbers and capitalised names (not the first word) occur in the chapter text."""
    from engine.title_variants import ungrounded_names, ungrounded_numbers
    return bool(title) and not ungrounded_numbers(title, text) and not ungrounded_names(title, text)


def title_chapters(chapters, highlights, transcript_segments, ask=None):
    """Add "title" to every chapter: LLM title when it is grounded in the chapter's speech, otherwise a keyword title."""
    texts = [chapter_text(c, highlights, transcript_segments) for c in chapters]
    from_llm = llm_titles(texts, ask=ask) or [""] * len(chapters)
    for i, c in enumerate(chapters):
        t = from_llm[i]
        if not grounded_title(t, texts[i]):
            t = keyword_title(texts[i])
        c["title"] = t or f"Part {i + 1}"
    chapters[0]["title"] = chapters[0]["title"] or "Intro"
    return chapters


def timestamp(seconds):
    """0 -> '0:00', 75 -> '1:15', 3725 -> '1:02:05' (YouTube accepts m:ss and h:mm:ss)."""
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def format_chapters(chapters):
    """The description block: one 'm:ss Title' line per chapter."""
    return "\n".join(f"{timestamp(c['start'])} {c['title']}" for c in chapters)


def chapters_for_reel(highlights, transcript_segments, xf=0.25, total=None, durations=None, ask=None):
    """Titled chapters for the highlights reel as [{"start", "end", "title", "timestamp"}], or [] when it is too short."""
    chapters = build_chapters(highlights, xf=xf, total=total, durations=durations)
    if not chapters:
        return []
    title_chapters(chapters, highlights, transcript_segments, ask=ask)
    return [{"start": round(c["start"], 2), "end": round(c["end"], 2), "title": c["title"], "timestamp": timestamp(c["start"])}
            for c in chapters]
