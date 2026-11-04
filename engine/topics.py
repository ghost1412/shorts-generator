"""Topic segmentation and diversity for highlight selection.

Without it, a talk that spends ten minutes on one subject can give three near-identical clips (the same point, made three
times) while a different good moment is left out. This module (pure Python, no model or network) does two things:

* `topic_segments`: a TextTiling-style split of the transcript into topics, from how much the vocabulary of neighbouring
  blocks of sentences overlaps.
* `diversify`: re-orders ranked candidates greedily so that a clip too similar to one already picked is skipped (near
  duplicate) or pushed down (same topic / overlapping wording), and a different moment can take its place.
"""
import math
import re
from collections import Counter

STOPWORDS = set("""a about above after again all also am an and any are as at be because been before being below between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his how i if in into is
it its just like me more most my no nor not now of off on once only or other our out over own same she should so some such than that
the their them then there these they this those through to too under until up very was we were what when where which while who whom
why will with would you your yeah okay um uh well really actually basically gonna kind sort thing things know mean right got get""".split())


def content_words(text):
    return [w for w in re.findall(r"[a-z0-9']+", str(text).lower()) if len(w) > 2 and w not in STOPWORDS]


def cosine(a, b):
    """Cosine similarity of two Counters of words (0 when either is empty)."""
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def clip_counter(transcript, start, end):
    """Word counts of what is said between `start` and `end`."""
    words = []
    for seg in (transcript or {}).get("segments", []):
        if float(seg.get("end", 0)) < start or float(seg.get("start", 0)) > end:
            continue
        inside = [w for w in (seg.get("words") or []) if start <= float(w.get("start", -1)) <= end]
        words.extend(w.get("word", "") for w in inside) if inside else words.append(seg.get("text", ""))
    return Counter(content_words(" ".join(words)))


def topic_segments(transcript, block=4, min_topic_seconds=40.0):
    """[(start, end)] topic spans covering the transcript. Boundaries sit where the vocabulary of the `block` sentences before
    and after a point overlaps least (clearly below the average); topics shorter than `min_topic_seconds` are merged."""
    from engine.highlight_quality import sentence_spans
    spans = sentence_spans(transcript)
    if len(spans) < 2 * block:
        return [(spans[0][0], spans[-1][1])] if spans else []
    counters = [Counter(content_words(t)) for _, _, t in spans]
    sims = []                                    # similarity across the gap after sentence i (i = block-1 .. n-block-1)
    for i in range(block - 1, len(spans) - block):
        left, right = Counter(), Counter()
        for c in counters[i - block + 1:i + 1]:
            left.update(c)
        for c in counters[i + 1:i + 1 + block]:
            right.update(c)
        sims.append((i, cosine(left, right)))
    if not sims:
        return [(spans[0][0], spans[-1][1])]
    values = [v for _, v in sims]
    mean = sum(values) / len(values)
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    cut_after = [i for k, (i, v) in enumerate(sims)
                 if v < mean - 0.5 * std and v <= min(values[max(0, k - 2):k + 3])]       # a local dip, clearly low
    topics, begin = [], spans[0][0]
    for i in cut_after:
        end = spans[i][1]
        if end - begin >= min_topic_seconds:
            topics.append((begin, end))
            begin = spans[i + 1][0]
    topics.append((begin, spans[-1][1]))
    if len(topics) > 1 and topics[-1][1] - topics[-1][0] < min_topic_seconds:        # a tiny tail joins the previous topic
        last = topics.pop()
        topics[-1] = (topics[-1][0], last[1])
    return topics


def topic_of(topics, start, end):
    """Index of the topic that contains the middle of the clip (-1 when there is none)."""
    mid = (start + end) / 2.0
    for i, (s, e) in enumerate(topics):
        if s <= mid <= e:
            return i
    return -1


def diversify(highlights, transcript, dup_threshold=0.6, sim_penalty=40.0, topic_penalty=8.0, score_key="final_score"):
    """Candidates re-ordered best-first with repetition pushed down. Near-duplicates (wording similarity >= dup_threshold with an
    already chosen clip) are dropped. A clip's effective score is lowered by `sim_penalty` x its overlap in wording above 0.15
    and by `topic_penalty` when it shares a topic with a chosen clip, so a slightly weaker clip on a new subject can win.
    Each returned clip gets `topic` (index) and `diversity_penalty`; the input list is not modified."""
    if len(highlights) < 2:
        return list(highlights)
    topics = topic_segments(transcript)
    pool = []
    for h in highlights:
        s, e = float(h["start"]), float(h["end"])
        pool.append({"h": h, "score": float(h.get(score_key, h.get("viral_score", 0)) or 0),
                     "words": clip_counter(transcript, s, e), "topic": topic_of(topics, s, e)})
    chosen, order = [], []
    remaining = pool[:]
    while remaining:
        best, best_eff, best_pen = None, -1e9, 0.0
        for c in remaining:
            sim = max((cosine(c["words"], k["words"]) for k in chosen), default=0.0)
            if sim >= dup_threshold:
                continue
            same = any(c["topic"] != -1 and c["topic"] == k["topic"] for k in chosen)
            pen = sim_penalty * max(0.0, sim - 0.15) + (topic_penalty if same else 0.0)
            if c["score"] - pen > best_eff:
                best, best_eff, best_pen = c, c["score"] - pen, pen
        if best is None:                          # everything left duplicates a chosen clip
            break
        remaining.remove(best)
        chosen.append(best)
        order.append(dict(best["h"], topic=best["topic"], diversity_penalty=round(best_pen, 2)))
    return order
