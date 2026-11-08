"""Keep the puzzle formats (odd one out, find it) from repeating themselves.

`fresh(options, kind)` picks at random from `options` but skips what was used in the last runs of that `kind`
(a small JSON file in the user's cache folder, never in the repo). When everything was used recently the oldest-used
option is allowed again, so a short list still works.
"""
import json
import os
import random

KEEP = 60                 # remembered picks per kind


def _path():
    return os.path.join(os.path.expanduser("~"), ".cache", "shortsflow", "puzzle_history.json")


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def fresh(options, kind, rng=random, path=None, remember=True):
    """One of `options` (strings) that was not picked recently for `kind`; the pick is remembered."""
    options = list(options)
    if not options:
        raise ValueError("no options")
    path = path or _path()
    data = _load(path)
    recent = [x for x in data.get(kind, []) if isinstance(x, str)]
    recent_window = recent[-max(1, len(options) // 2):]                   # avoid the last half of the list, so picks stay random
    free = [o for o in options if o not in recent_window]
    pick = rng.choice(free) if free else rng.choice(options)
    if remember:
        data[kind] = (recent + [pick])[-KEEP:]
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except OSError:
            pass
    return pick
