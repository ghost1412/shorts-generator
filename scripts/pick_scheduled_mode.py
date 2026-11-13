"""Pick the content mode for one scheduled (cron) run, by weighted chance.

Scheduled runs used to be pinned to FACTS ("spot the lie"), so the channel only ever got that format.
This picks a mode at random from a safe list: modes that need no topic, avatar or extra audio asset.

Control it with the repo variable SCHEDULED_MODE (the workflow passes it as the first argument):
  (empty) or MIX      weighted pick from DEFAULT_WEIGHTS
  FACTS, WYR, ...     always that one mode (the old behaviour)
  WYR:30,FACTS:10     your own weights (NAME:weight, comma separated); unknown names are ignored

Weights are met exactly, in a fixed rotation, not by dice: every 4-hour slot gets the next mode of a smooth weighted round-robin, so the
same mode is never picked twice in a row (with the default weights FACTS comes about every fourth run). Random draws gave streaks, for
example three "spot the lie" runs in a row, which looks like a broken picker even when it is not.

Prints the chosen mode on stdout. Exits 0 always (falls back to FACTS) so a typo cannot stop the daily run.
"""
import random
import sys
import time

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
SLOT_SECONDS = 4 * 3600                   # the daily workflow runs every 4 hours
SLOT_EPOCH = 1_793_491_200                # 2026-11-01 00:00 UTC: slot numbers start here, so the rotation is short to compute


def slot_number(now=None):
    return max(0, int(((time.time() if now is None else now) - SLOT_EPOCH) // SLOT_SECONDS))


def rotation_pick(weights, n):
    """The mode of slot `n` in a smooth weighted round-robin over `weights` (deterministic: the same slot always gives the same mode).
    Each step every mode gains its weight, the leader is chosen and pays back the total, so picks are spread as evenly as the weights allow.
    The mode of the step before is skipped (the restart of the cycle would otherwise repeat the first mode), unless one mode holds more than
    half of the weight: then repeats cannot be avoided and the weights win."""
    names = list(weights)
    total = float(sum(weights.values()))
    current = {k: 0.0 for k in names}
    choice = None
    avoid_repeat = len(names) > 1 and 2 * max(weights.values()) <= total
    for _ in range(int(n) + 1):
        for k in names:
            current[k] += weights[k]
        pool = [k for k in names if k != choice] if avoid_repeat else names
        choice = max(pool, key=lambda k: current[k])
        current[choice] -= total
    return choice


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


def pick(spec="", rng=random, slot=None):
    """`slot` given: the rotation (what the workflow uses). Without it: a weighted random draw (kept for manual use and tests)."""
    spec = (spec or "").strip()
    if spec.upper() in ("", "MIX"):
        weights = DEFAULT_WEIGHTS
    elif "," not in spec and ":" not in spec:
        return spec.upper()                      # a single fixed mode
    else:
        weights = parse_weights(spec) or DEFAULT_WEIGHTS
    if slot is not None:
        return rotation_pick(weights, slot)
    return rng.choices(list(weights), weights=list(weights.values()))[0]


if __name__ == "__main__":
    try:
        print(pick(sys.argv[1] if len(sys.argv) > 1 else "", slot=slot_number()))
    except Exception:
        print(FALLBACK)
