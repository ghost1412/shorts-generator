"""Clip quality report for finished runs (no LLM, no network).

    python scripts/clip_benchmark.py sessions/run_a sessions/run_b [--gold gold.json] [--json out.json]

Each folder needs transcript.json and results.json (what a normal run writes). With --gold (a file {"<video file name>": [[start, end], ...]})
the report also shows recall and precision against moments you chose by hand. --picture also checks the clip videos (face in frame,
face centred, crop jitter, silent share; engine/clip_picture.py). Compare two reports from before and after a change.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import clip_quality  # noqa: E402

COLUMNS = [("clips", "clips"), ("median_length_s", "len s"), ("length_in_range", "len ok"), ("starts_at_sentence", "start ok"),
           ("ends_at_sentence", "end ok"), ("overlap_s", "overlap"), ("spread", "spread"), ("median_words_per_s", "words/s"),
           ("titles_grounded", "titles ok"), ("gaps_s", "gaps s"), ("cut_s", "cut s"), ("reel_s", "reel s"), ("target_s", "target s"), ("reel_file_s", "file s"), ("recall", "recall"), ("precision", "prec"),
           ("face_found", "face"), ("centered", "centred"), ("jitter", "jitter"), ("silence", "silence")]


def fmt(v):
    return "-" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def table(rows):
    cols = [(k, h) for k, h in COLUMNS if any(k in r for r in rows)]
    head = ["session"] + [h for _, h in cols]
    lines = [[r["session"][:28]] + [fmt(r.get(k)) for k, _ in cols] for r in rows]
    widths = [max(len(str(x[i])) for x in [head] + lines) for i in range(len(head))]
    return "\n".join("  ".join(str(c).ljust(w) for c, w in zip(row, widths)) for row in [head] + lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--gold", help="json file {video file name: [[start, end], ...]} of moments a person picked")
    ap.add_argument("--json", help="also write the report here")
    ap.add_argument("--picture", action="store_true", help="also open the clip videos: face found, face centred, crop jitter, silence")
    a = ap.parse_args(argv)
    gold = json.load(open(a.gold, encoding="utf-8")) if a.gold else None
    rows = [r for r in (clip_quality.report(s, gold, picture=a.picture) for s in a.sessions) if r]
    skipped = len(a.sessions) - len(rows)
    if not rows:
        print("No readable runs (each folder needs transcript.json and results.json).")
        return 1
    print(table(rows))
    if skipped:
        print(f"({skipped} folder(s) skipped: no readable transcript.json / results.json)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
