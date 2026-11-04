"""Stat pop-ups: when a speaker says a striking number, show it big on screen for a moment.

"Most people waste $200 a month", "73 percent of ...", "in 10 years": editors put the number on screen the instant it is said.
`find_stats` reads the clip's word timings and returns the few numbers worth showing:

    [{"start": 4.2, "end": 5.9, "text": "$200"}, {"start": 11.0, "end": 12.7, "text": "73%"}]

A number qualifies when it has a currency symbol or a percent, or is at least 100, or is followed by a unit word (percent, million,
dollars, times ...). Years, single small numbers ("3 tips") and numbers in the first second or the last moment are skipped, and at
most one per `min_spacing` seconds is kept so the screen never fills with numbers.
"""
import re

NUMBER = re.compile(r"^([$€£]?)(\d[\d,]*(?:\.\d+)?)([%kKmMbB]?)$")
UNITS = {"percent": "%", "%": "%", "million": " MILLION", "billion": " BILLION", "thousand": " THOUSAND", "trillion": " TRILLION",
         "dollars": "$", "dollar": "$", "bucks": "$", "euros": "€", "pounds": "£", "times": "X", "x": "X",
         "years": " YEARS", "months": " MONTHS", "weeks": " WEEKS", "days": " DAYS", "hours": " HOURS", "minutes": " MINUTES"}
TIME_UNITS = {" YEARS", " MONTHS", " WEEKS", " DAYS", " HOURS", " MINUTES"}      # only striking from 5 up ("10 years", not "2 days")
SHOW_SECONDS = 1.7
MIN_SPACING = 4.0
EDGE_START = 1.0
EDGE_END = 1.0


def _clean(word):
    return str(word).strip().strip(".,!?;:\"'()[]")


def _value(digits):
    try:
        return float(digits.replace(",", ""))
    except ValueError:
        return 0.0


def find_stats(words, duration, max_per_minute=6, min_spacing=MIN_SPACING):
    """[{start, end, text}] on the clip's timeline, sorted, for the numbers worth showing."""
    if not words or not duration or duration < 5.0:
        return []
    found = []
    for i, w in enumerate(words):
        token = _clean(w.get("word", ""))
        m = NUMBER.match(token)
        if not m:
            continue
        symbol, digits, suffix = m.groups()
        value = _value(digits)
        nxt = _clean(words[i + 1].get("word", "")).lower() if i + 1 < len(words) else ""
        unit = UNITS.get(nxt) if nxt else None
        is_year = (not symbol and not suffix and not unit and "," not in digits and "." not in digits
                   and 1900 <= value <= 2100)
        if unit in TIME_UNITS and value < 5:
            unit = None
        qualifies = bool(symbol or suffix == "%" or value >= 100 or unit)
        if is_year or not qualifies or value <= 0:
            continue
        start = float(w.get("start", 0.0))
        if start < EDGE_START or start > duration - EDGE_END:
            continue
        # compose the text to show
        text = token
        if unit == "%":
            text = f"{digits}%"
        elif unit in ("$", "€", "£"):
            text = f"{unit}{digits}"
        elif unit == "X":
            text = f"{digits}X"
        elif unit:
            text = f"{symbol}{digits}{unit}"
        found.append({"start": round(start, 3), "end": round(min(start + SHOW_SECONDS, duration - 0.3), 3), "text": text.upper(),
                      "_v": value})
    # keep the biggest numbers first when they crowd each other, then restore time order
    cap = max(1, int(duration / 60.0 * max_per_minute + 0.5), 1 if duration < 20 else 2)
    chosen = []
    for s in sorted(found, key=lambda s: (-s["_v"], s["start"])):
        if len(chosen) >= cap:
            break
        if all(abs(s["start"] - c["start"]) >= min_spacing for c in chosen):
            chosen.append(s)
    return [{k: v for k, v in s.items() if k != "_v"} for s in sorted(chosen, key=lambda s: s["start"])]
