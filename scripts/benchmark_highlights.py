"""Highlight boundary benchmark (offline, no video / LLM / network).

    python scripts/benchmark_highlights.py            # raw LLM-style picks vs boundary-snapped picks, 20 seeded transcripts
    python scripts/benchmark_highlights.py --seeds 50
    python scripts/benchmark_highlights.py --transcript sessions/x/transcript.json   # sentence stats of a real transcript
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine.highlight_bench import run  # noqa: E402
from engine.highlight_quality import sentence_spans, snap_highlights  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--transcript", help="a real transcript.json: print how it splits into sentences")
    a = ap.parse_args()
    if a.transcript:
        with open(a.transcript, encoding="utf-8") as f:
            spans = sentence_spans(json.load(f))
        lens = [e - s for s, e, _ in spans]
        print(f"{len(spans)} sentences, median {sorted(lens)[len(lens) // 2]:.1f} s, longest {max(lens):.1f} s")
        return
    raw, snapped = run(snap_highlights, seeds=range(a.seeds))
    print(f"{'metric':<20}{'raw':>8}{'snapped':>10}")
    for k in raw:
        print(f"{k:<20}{raw[k]:>8.3f}{snapped[k]:>10.3f}")


if __name__ == "__main__":
    main()
