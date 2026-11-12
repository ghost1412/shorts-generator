"""Offline benchmark for highlight boundaries (no video, no LLM, no network).

It builds seeded synthetic transcripts with known "best moments" (a run of sentences ending in a payoff), simulates the
sloppy start/end times an LLM or the heuristic fallback gives (mid-sentence starts, ends before the payoff), and measures
how well a post-processing step (boundary snapping) repairs them. Because the picks are synthetic, the numbers measure
OUR boundary handling, not a model's taste; a labelled real transcript can be added the same way
(see scripts/benchmark_highlights.py --transcript).

Run it:  python scripts/benchmark_highlights.py
"""
import random

FILLER_OPENERS = ["So, um, okay.", "Well, you know.", "Alright, so.", "Okay, so yeah."]
SUBJECTS = ["the rent", "your phone plan", "this recipe", "the old camera", "a savings account", "that habit", "the new update"]


def build_transcript(seed, sentences=40):
    """(transcript dict, labels) - labels = [{start, end, payoff_end, first, last}] for 3 best moments."""
    rng = random.Random(seed)
    t, segs, spans, texts = 0.0, [], [], []
    for i in range(sentences):
        if rng.random() < 0.18:                     # a filler sentence before many sentences ("So, um, okay.")
            n_text = rng.choice(FILLER_OPENERS)
        else:
            n = rng.randint(6, 14)
            subj = rng.choice(SUBJECTS)
            n_text = f"Here is a point about {subj} number {i} " + " ".join(rng.choice(["really", "matters", "often", "most", "people", "never", "notice", "it"]) for _ in range(n - 7)) if n > 7 else f"Here is a point about {subj}"
            n_text = n_text.strip() + rng.choice([".", ".", ".", "?", "!"])
        words, start = [], t
        for w in n_text.split():
            d = rng.uniform(0.22, 0.42)
            words.append({"word": " " + w, "start": round(t, 2), "end": round(t + d, 2), "probability": 0.9})
            t += d + 0.03
        spans.append((round(start, 2), round(words[-1]["end"], 2), n_text))
        texts.append(n_text)
        segs.append({"start": round(start, 2), "end": round(words[-1]["end"], 2), "text": n_text, "words": words})
        t += rng.uniform(0.35, 1.0)                 # pause between sentences
    # whisper-like segments hold 2-3 sentences: merge neighbours so a segment edge is not always a sentence edge
    merged = []
    i = 0
    while i < len(segs):
        take = rng.choice([1, 2, 3])
        chunk = segs[i:i + take]
        merged.append({"start": chunk[0]["start"], "end": chunk[-1]["end"], "text": " ".join(c["text"] for c in chunk),
                       "words": [w for c in chunk for w in c["words"]]})
        i += take
    labels, cursor = [], 2
    for _ in range(3):
        n = rng.randint(6, 9)
        first = cursor + rng.randint(0, 2)
        last = min(first + n, sentences - 2)
        if last - first < 5:
            break
        labels.append({"start": spans[first][0], "end": spans[last][1], "payoff_end": spans[last][1], "first": first, "last": last})
        cursor = last + 3
    return {"segments": merged}, labels, spans, texts


def sloppy_picks(labels, seed):
    """What a coarse LLM / heuristic hands back: edges off by a few seconds, usually mid-sentence."""
    rng = random.Random(seed * 7919 + 1)
    return [{"start": round(max(0.0, lab["start"] + rng.uniform(-4.0, 4.0)), 2),
             "end": round(lab["end"] + rng.uniform(-5.0, 3.0), 2), "viral_score": 80} for lab in labels]


def _nearest(value, points):
    return min(abs(value - p) for p in points)


def score(clips, labels, spans, texts):
    """Per-clip metrics averaged over clips."""
    starts = [s for s, _, _ in spans]
    ends = [e for _, e, _ in spans]
    rows = []
    for clip, lab in zip(clips, labels):
        s, e = float(clip["start"]), float(clip["end"])
        first_sentence = next((txt for (ss, ee, txt) in spans if ss >= s - 0.15), "")
        inter = max(0.0, min(e, lab["end"]) - max(s, lab["start"]))
        union = max(e, lab["end"]) - min(s, lab["start"])
        rows.append({
            "start_on_sentence": _nearest(s, starts) <= 0.15,
            "end_on_sentence": _nearest(e, ends) <= 0.6,           # a short tail after the last word counts
            "payoff_included": e >= lab["payoff_end"] - 0.05,
            "leadin_free": first_sentence not in FILLER_OPENERS,
            "iou": inter / union if union else 0.0,
            "duration_ok": 8.0 <= e - s <= 59.9,
        })
    n = max(1, len(rows))
    return {k: sum(float(r[k]) for r in rows) / n for k in rows[0]} if rows else {}


def run(snap_fn, seeds=range(20)):
    """(raw metrics, snapped metrics) averaged over the seeded transcripts; snap_fn(highlights, transcript) -> highlights."""
    agg_raw, agg_snap, count = {}, {}, 0
    for seed in seeds:
        transcript, labels, spans, texts = build_transcript(seed)
        if not labels:
            continue
        raw = sloppy_picks(labels, seed)
        snapped = snap_fn([dict(c) for c in raw], transcript)
        for agg, clips in ((agg_raw, raw), (agg_snap, snapped)):
            for k, v in score(clips, labels, spans, texts).items():
                agg[k] = agg.get(k, 0.0) + v
        count += 1
    return ({k: round(v / count, 3) for k, v in agg_raw.items()}, {k: round(v / count, 3) for k, v in agg_snap.items()})
