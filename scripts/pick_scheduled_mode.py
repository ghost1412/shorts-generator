"""Pick the content mode for one scheduled (cron) run, by weighted chance.

Scheduled runs used to be pinned to FACTS ("spot the lie"), so the channel only ever got that format.
This picks a mode at random from a safe list: modes that need no topic, avatar or extra audio asset.

Control it with the repo variable SCHEDULED_MODE (the workflow passes it as the first argument):
  (empty) or MIX      weighted pick from DEFAULT_WEIGHTS
  FACTS, WYR, ...     always that one mode (the old behaviour)
  WYR:30,FACTS:10     your own weights (NAME:weight, comma separated); unknown names are ignored

Prints the chosen mode on stdout. Exits 0 always (falls back to FACTS) so a typo cannot stop the daily run.
"""
import random
import sys

DEFAULT_WEIGHTS = {
    "FACTS": 25,        # spot the lie
    "WYR": 15,          # this or that
    "EMOJI_GUESS": 15,
    "ODD_ONE_OUT": 10,
    "FIND_IT": 8,
    "TRIVIA": 8,
    "RIDDLE": 8,
    "TOP_5": 6,
    "STORY": 5,
}
FALLBACK = "FACTS"


def parse_weights(spec):
    """'WYR:30,FACTS' -> {'WYR': 30, 'FACTS': 1}; None when the spec is not a weight list."""
    out = {}
    for part in spec.split(","):
        name, _, w = part.strip().partition(":")
        name = name.strip().upper()
        if not name:
            continue
        try:
            weight = float(w) if w.strip() else 1.0
        except ValueError:
            continue
        if weight > 0:
            out[name] = weight
    return out or None


def pick(spec="", rng=random):
    spec = (spec or "").strip()
    if spec.upper() in ("", "MIX"):
        weights = DEFAULT_WEIGHTS
    elif "," not in spec and ":" not in spec:
        return spec.upper()                      # a single fixed mode
    else:
        weights = parse_weights(spec) or DEFAULT_WEIGHTS
    return rng.choices(list(weights), weights=list(weights.values()))[0]


if __name__ == "__main__":
    try:
        print(pick(sys.argv[1] if len(sys.argv) > 1 else ""))
    except Exception:
        print(FALLBACK)
